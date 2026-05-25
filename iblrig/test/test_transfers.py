import copy
import logging
import random
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from packaging import version

import ibllib
import iblrig.commands
import iblrig.neurophotometrics
import iblrig.path_helper
import iblrig.raw_data_loaders
from ibllib.io import session_params
from ibllib.tests.fixtures.utils import populate_raw_spikeglx
from iblrig.path_helper import HardwareSettings, load_pydantic_yaml
from iblrig.test.base import TASK_KWARGS
from iblrig.transfer_experiments import BehaviorCopier, CopyState, EphysCopier, SessionCopier, VideoCopier
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session

logger = logging.getLogger(__name__)


def _create_behavior_session(ntrials=None, hard_crash=False, kwargs=None):
    """
    Creates a generic session in a tempdir. If ntrials is specified, create a jsonable file with ntrials
    and update the task settings
    :param temp_dir:
    :param ntrials:
    :param hard_crash: if True, simulates a hardcrash by not labeling the session end time and ntrials
    :return:
    """
    kwargs = kwargs or TASK_KWARGS
    session = Session(**kwargs)
    session.create_session()
    # This opens a log file in the session path for writing to. We immediately close it so it doesn't
    # interfere with the copy routine.
    session._remove_file_loggers()
    session.paths.SESSION_FOLDER.joinpath('raw_video_data').mkdir(parents=True)
    session.paths.SESSION_FOLDER.joinpath('raw_video_data', 'tutu.avi').touch()
    if ntrials is not None:
        with open(Path(__file__).parent.joinpath('fixtures', 'task_data_short.jsonable')) as fid:
            lines = fid.readlines()
        with open(Path(session.paths.DATA_FILE_PATH), 'w') as fid:
            fid.writelines(random.choice(lines) for _ in range(ntrials))
        if not hard_crash:
            session.session_info['NTRIALS'] = ntrials
            session.session_info['SESSION_END_TIME'] = session.session_info['SESSION_START_TIME']
            session.save_task_parameters_to_json_file()
    # we need to remove the file logging otherwise the hash of the logfile will not match
    session._remove_file_loggers()
    return session


class TestIntegrationTransferExperimentsBase(unittest.TestCase):
    """this base class copier testing"""

    def setUp(self):
        self.iblrig_settings = load_pydantic_yaml(iblrig.path_helper.RigSettings, 'iblrig_settings_template.yaml')
        self.hardware_settings = load_pydantic_yaml(iblrig.path_helper.HardwareSettings, 'hardware_settings_template.yaml')
        self.td = tempfile.TemporaryDirectory()
        self.session_kwargs = copy.deepcopy(TASK_KWARGS)
        self.iblrig_settings.update(
            {
                'iblrig_remote_data_path': Path(self.td.name).joinpath('remote'),
                'iblrig_local_data_path': Path(self.td.name).joinpath('behavior'),
                'ALYX_LAB': 'cortexlab',
            }
        )
        self.session_kwargs['iblrig_settings'] = self.iblrig_settings

    def tearDown(self):
        self.td.cleanup()

    def return_settings_from_template(self, *args, filename=None, **kwargs):
        """side effect for mocking: return the iblrig / hardware settings
        from the respective template file"""
        if filename.name.endswith('hardware_settings.yaml'):
            return self.hardware_settings
        elif filename.name.endswith('iblrig_settings.yaml'):
            return self.iblrig_settings
        else:
            raise FileNotFoundError(f'unknown settings file: {filename}')


class TestIntegrationTransferExperimentsPhotometry(TestIntegrationTransferExperimentsBase):
    """for testing the photometry"""

    neurophotometrics_hardware_defaults = {'FRAMECLOCK_CHANNEL': 1}

    def return_settings_from_template(self, *args, filename=None, **kwargs):
        """for mocking: return the iblrig / hardware settings from the respective
        template file"""
        if filename.name.endswith('hardware_settings.yaml'):
            self.hardware_settings['device_neurophotometrics'] = self.neurophotometrics_hardware_defaults
            return self.hardware_settings
        elif filename.name.endswith('iblrig_settings.yaml'):
            return self.iblrig_settings
        else:
            raise FileNotFoundError(f'unknown settings file: {filename}')

    def create_fake_data(
        self,
        neurophotometrics_start_time: datetime | None = None,
        sync_mode: str = 'bpod',
        daqami_offset_timedelta: timedelta | None = None,
    ) -> Path:
        """creates photometry data for testing the copier, returns the path of the
        session folder that was created"""
        if neurophotometrics_start_time is None:
            neurophotometrics_start_time = datetime.now()

        # create neurophotometrics folder
        neurophotometrics_folder = (
            self.iblrig_settings['iblrig_local_data_path']
            / 'neurophotometrics'
            / neurophotometrics_start_time.strftime('%Y-%m-%d')
            / neurophotometrics_start_time.strftime('T%H%M%S')
        )
        neurophotometrics_folder.mkdir(exist_ok=True, parents=True)

        if sync_mode == 'bpod':
            # creating fake digital_inputs.csv

            # NOTE
            # ideally, we would import this definition from iblphotometry
            # iblphotometry should not be a dependency of iblrig
            # photometry (or any modality) specific code should live in a different module/repo
            # that extends iblrig and can import iblphotometry
            cols_dtypes = dict(
                ChannelName=str,
                Channel='int8',
                AlwaysTrue='bool',
                SystemTimestamp='float64',
                ComputerTimestamp='float64',
            )
            cols = list(cols_dtypes.keys())
            # create the digital inputs file
            digital_inputs_df = pd.DataFrame(np.random.randn(10, len(cols)), columns=cols)
            for col, dtype in cols_dtypes.items():
                digital_inputs_df[col] = digital_inputs_df[col].astype(dtype)
            digital_inputs_df.to_csv(neurophotometrics_folder / 'digital_inputs.csv')

        elif sync_mode == 'daqami':
            # creating daqami sync data created with a time offset
            if daqami_offset_timedelta is None:
                # by default, daqami is assumed to have started 5 minutes before the neurophotometrics
                daqami_offset_timedelta = timedelta(min=-5)
            daqami_start_time = neurophotometrics_start_time + daqami_offset_timedelta

            # creating fake daq sync file
            daqami_folder = (
                self.iblrig_settings['iblrig_local_data_path']
                / 'daqami'
                / daqami_start_time.strftime('%Y-%m-%d')
                / daqami_start_time.strftime('T%H%M')
            )
            daqami_folder.mkdir(parents=True, exist_ok=True)
            # in order to later test if the correct daq files were copied, the timestamp of their creation
            # is written into the file (as it is stripped from the filename that ispresent at the local
            # but not at the remote)
            with open(daqami_folder / 'daqami_sync.tdms', 'w') as file_handle:
                file_handle.write(daqami_start_time.isoformat())

        # creating fake photometry data file
        # see note above
        cols_dtypes = dict(
            FrameCounter='int64',
            SystemTimestamp='float64',
            LedState='int16',
            ComputerTimestamp='float64',
            Region1G='float64',
            Region2G='float64',
        )
        cols = list(cols_dtypes.keys())
        raw_photometry_df = pd.DataFrame(np.random.randn(10, len(cols)), columns=cols)
        for col, dtype in cols_dtypes.items():
            raw_photometry_df[col] = raw_photometry_df[col].astype(dtype)

        (neurophotometrics_folder / 'raw_photometry').mkdir(exist_ok=True)
        raw_photometry_df.to_csv(neurophotometrics_folder / 'raw_photometry' / 'raw_photometry.csv', index=False)
        logger.info('Created fake photometry data in %s', neurophotometrics_folder)
        return neurophotometrics_folder

    def test_copier_bpod(self):
        # DEBUG to check: timestamp of created session
        session = _create_behavior_session(ntrials=50, kwargs=self.session_kwargs)
        session_start_time = datetime.fromisoformat(session.session_info['SESSION_START_TIME'])

        # create several fake photometry datasets
        # this is to assure that the correct dataset is picked by the copier
        neurophotometrics_start_time_a = session_start_time + timedelta(hours=-1)
        neurophotometrics_start_time_b = session_start_time + timedelta(minutes=-5)
        neurophotometrics_start_time_c = session_start_time + timedelta(hours=+2)

        _ = self.create_fake_data(neurophotometrics_start_time=neurophotometrics_start_time_a)
        local_photometry_folder_b = self.create_fake_data(
            neurophotometrics_start_time=neurophotometrics_start_time_b
        )  # < this is the relevant one
        _ = self.create_fake_data(neurophotometrics_start_time=neurophotometrics_start_time_c)

        # copy data
        with mock.patch('iblrig.path_helper._load_settings_yaml', side_effect=self.return_settings_from_template):
            iblrig.neurophotometrics.init_neurophotometrics_subject(
                subject='test_subject',
                rois=['Region1G', 'Region2G'],
                locations=['VTA', 'SNc'],
                sync_channel=0,
                sync_mode='bpod',
            )
            (copier,) = iblrig.commands.transfer_data(tag='neurophotometrics')
            self.assertEqual(copier.state, CopyState.COMPLETE)

        # test if the files were copied
        assert (copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.channels.csv').exists()
        assert (copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.digitalInputs.pqt').exists()
        assert (copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.raw.pqt').exists()

        # verify the contents of the raw photometry files
        data_raw_local = pd.read_csv(local_photometry_folder_b / 'raw_photometry' / 'raw_photometry.csv')
        data_raw_remote = pd.read_parquet(
            copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.raw.pqt'
        )
        pd.testing.assert_frame_equal(data_raw_local, data_raw_remote, check_dtype=False)

        # verify the contents of the digital input files
        assert (copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.digitalInputs.pqt').exists()
        data_digital_inputs_local = pd.read_csv(local_photometry_folder_b / 'digital_inputs.csv')
        data_digital_inputs_remote = pd.read_parquet(
            copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.digitalInputs.pqt'
        )
        pd.testing.assert_frame_equal(data_digital_inputs_local, data_digital_inputs_remote, check_dtype=False)

    def test_copier_daq(self):
        session = _create_behavior_session(ntrials=50, kwargs=self.session_kwargs)
        session_start_time = datetime.fromisoformat(session.session_info['SESSION_START_TIME'])

        # create several fake photometry datasets
        # this is to assure that the correct dataset is picked by the copier
        neurophotometrics_start_time_a = session_start_time + timedelta(hours=-1)
        neurophotometrics_start_time_b = session_start_time + timedelta(minutes=-5)
        neurophotometrics_start_time_c = session_start_time + timedelta(hours=+1)

        daqami_offset_a = timedelta(hours=-2)  # 2h before the first neurophotometrics
        daqami_offset_b = timedelta(minutes=-10)  # 10 minutes before the session of interest
        daqami_offset_c = timedelta(minutes=-30)  # 30 minutes before the last neurophotometrics session

        _ = neurophotometrics_start_time_a + daqami_offset_a
        daqami_start_time_b = neurophotometrics_start_time_b + daqami_offset_b
        _ = neurophotometrics_start_time_c + daqami_offset_c

        _ = self.create_fake_data(
            neurophotometrics_start_time=neurophotometrics_start_time_a,
            daqami_offset_timedelta=daqami_offset_a,
            sync_mode='daqami',
        )
        local_photometry_folder_b = self.create_fake_data(
            neurophotometrics_start_time=neurophotometrics_start_time_b,
            daqami_offset_timedelta=daqami_offset_b,
            sync_mode='daqami',
        )  # < this is the relevant one
        _ = self.create_fake_data(
            neurophotometrics_start_time=neurophotometrics_start_time_c,
            daqami_offset_timedelta=daqami_offset_c,
            sync_mode='daqami',
        )

        # copy data
        with mock.patch('iblrig.path_helper._load_settings_yaml', side_effect=self.return_settings_from_template):
            iblrig.neurophotometrics.init_neurophotometrics_subject(
                subject='test_subject',
                rois=['Region1G', 'Region2G'],
                locations=['VTA', 'SNc'],
                sync_channel=0,
                sync_mode='daqami',
            )
            (copier,) = iblrig.commands.transfer_data(tag='neurophotometrics')
            self.assertEqual(copier.state, CopyState.COMPLETE)

        # check that the correct data was copied
        assert (copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.raw.pqt').exists()
        # check raw data
        data_raw_local = pd.read_csv(local_photometry_folder_b / 'raw_photometry' / 'raw_photometry.csv')
        data_raw_remote = pd.read_parquet(
            copier.remote_session_path / 'raw_photometry_data' / '_neurophotometrics_fpData.raw.pqt'
        )
        pd.testing.assert_frame_equal(data_raw_local, data_raw_remote, check_dtype=False)

        # check daq data
        local_daqami_folder = self.iblrig_settings['iblrig_local_data_path'] / 'daqami'
        local_daqami_file = (
            local_daqami_folder
            / daqami_start_time_b.strftime('%Y-%m-%d')
            / daqami_start_time_b.strftime('T%H%M')
            / 'daqami_sync.tdms'
        )
        remote_daqami_file = copier.remote_session_path / 'raw_photometry_data' / '_mcc_DAQdata.raw.tdms'
        with open(local_daqami_file) as file_handle:
            daqami_timestamp_local = file_handle.readlines()
        with open(remote_daqami_file) as file_handle:
            daqami_timestamp_remote = file_handle.readlines()

        assert daqami_timestamp_local == daqami_timestamp_remote


class TestIntegrationTransferExperiments(TestIntegrationTransferExperimentsBase):
    """This test emulates the `transfer_data` command as run on the rig."""

    def test_behavior_copy_complete_session(self):
        """
        Here there are 2 cases, one is about a complete session, the other is about a session that crashed
        but is still valid (i.e. more than 42 trials)
        In this case both sessions should end up on the remote path with a copy state of 3
        """
        self.assertRaises(ValueError, iblrig.commands.transfer_data)  # Should raise without tag
        for hard_crash in [False, True]:
            session = _create_behavior_session(ntrials=50, hard_crash=hard_crash, kwargs=self.session_kwargs)
            session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
            with mock.patch('iblrig.path_helper._load_settings_yaml', side_effect=self.return_settings_from_template):
                iblrig.commands.transfer_data(
                    local_path=session.iblrig_settings['iblrig_local_data_path'],
                    remote_path=session.iblrig_settings['iblrig_remote_data_path'],
                    tag='behavior',
                )
            sc = BehaviorCopier(
                session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
            )
            self.assertEqual(sc.state, 3)
        # Check that the settings file is used when no path passed
        session = _create_behavior_session(ntrials=50, hard_crash=hard_crash, kwargs=self.session_kwargs)
        session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()

        with mock.patch('iblrig.path_helper._load_settings_yaml', side_effect=self.return_settings_from_template):
            iblrig.commands.transfer_data(tag='behavior')
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual(sc.state, 3)

    def test_behavior_copy(self):
        """Test behaviour copy with both dud and correct data."""
        # Create without task data
        session = _create_behavior_session(kwargs=self.session_kwargs)
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual(1, sc.state)
        today = datetime.today().isoformat()[:10]
        expected = [f'{today}_1_iblrig_test_subject@behavior.status_pending', f'{today}_1_iblrig_test_subject@behavior.yaml']
        remote_files = map(lambda x: x.name, filter(Path.is_file, session.paths.REMOTE_SUBJECT_FOLDER.rglob('*')))
        self.assertCountEqual(expected, remote_files)
        self.assertFalse(sc.copy_collections())  # fails because of missing task data
        self.assertEqual(0, sc.state)
        self.assertEqual([], list(filter(Path.is_file, session.paths.REMOTE_SUBJECT_FOLDER.rglob('*'))))

        # Create with task data
        session = _create_behavior_session(kwargs=self.session_kwargs, ntrials=50)
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual(1, sc.state)
        self.assertTrue(sc.copy_collections())
        self.assertEqual(2, sc.state)
        sc.finalize_copy(number_of_expected_devices=1)
        self.assertEqual(3, sc.state)  # this time it's all there and we move on

    def test_behavior_ephys_video_copy(self):
        """
        Unlike the integration test, the sessions here are made from scratch using an actual instantiated session
        :return:
        """
        # First create a behavior session
        task_kwargs = copy.deepcopy(self.session_kwargs)
        task_kwargs['hardware_settings'].update(
            {
                'device_cameras': None,
                'MAIN_SYNC': False,  # this is quite important for ephys sessions
            }
        )
        session = _create_behavior_session(kwargs=task_kwargs, ntrials=50)
        # SESSION_RAW_DATA_FOLDER is the one that gets copied
        folder_session_video = Path(self.td.name).joinpath('video', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
        folder_session_ephys = Path(self.td.name).joinpath('ephys', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
        folder_session_imaging = Path(self.td.name).joinpath('imaging', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])

        # Create an ephys acquisition
        n_probes = 2
        # prepare_ephys_session.py creates these empty folders
        folder_session_ephys.joinpath('raw_ephys_data').mkdir(parents=True)
        [folder_session_ephys.joinpath(f'probe{n:02}').mkdir() for n in range(n_probes)]
        # SpikeGLX then saves these files into the session folder
        populate_raw_spikeglx(folder_session_ephys, model='3B', n_probes=n_probes)
        # Create a video acquisition
        folder_session_video.joinpath('raw_video_data').mkdir(parents=True)
        for vname in ['body', 'left', 'right']:
            folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.frameData.bin').touch()
            folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.raw.avi').touch()

        # imaging computer (testing generic copier)
        folder_session_imaging.mkdir(parents=True)
        ic = SessionCopier(session_path=folder_session_imaging, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        description = {'mesoscope': {'mesoscope': {'collection': 'raw_imaging_data*', 'sync_label': 'chrono'}}}

        for i in range(2):
            collection = folder_session_imaging.joinpath(f'raw_imaging_data_{i:02}')
            collection.mkdir()
            for j in range(2):
                file = collection.joinpath(f'{datetime.today().isoformat()[:10]}_1_iblrig_test_subject_{j:02}.tif')
                with open(file, 'wb') as fp:
                    fp.write(j.to_bytes(24, byteorder='big', signed=False))
        self.assertEqual(0, ic.state)
        ic.initialize_experiment(description)

        # Test the copiers
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual('.status_pending', sc.glob_file_remote_copy_status().suffix)
        self.assertEqual(1, sc.state)
        sc.copy_collections()
        self.assertEqual(2, sc.state)
        self.assertEqual('.status_complete', sc.glob_file_remote_copy_status().suffix)
        sc.copy_collections()
        self.assertEqual(2, sc.state)
        sc.finalize_copy(number_of_expected_devices=None)
        self.assertEqual(2, sc.state)  # here we still don't have all devices so we stay in state 2

        vc = VideoCopier(session_path=folder_session_video, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        hws = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        vc.create_video_stub(hws['device_cameras']['default'])
        self.assertEqual(0, vc.state)
        vc.initialize_experiment()
        self.assertEqual(1, vc.state)
        vc.copy_collections()
        self.assertEqual(2, vc.state)
        sc.finalize_copy(number_of_expected_devices=None)
        self.assertEqual(2, vc.state)  # here we still don't have all devices so we stay in state 2

        ec = EphysCopier(session_path=folder_session_ephys, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual(0, ec.state)
        ec.initialize_experiment()
        self.assertEqual(1, ec.state)
        self.assertIn('sync', ec.experiment_description)
        ec.copy_collections()
        self.assertEqual(2, ec.state)
        # here it is a bit tricky; we want to safeguard finalizing the copy when the sync is different than bpod
        # so in this case, we expect the status to stay at 2 and a warning to be thrown
        sc.finalize_copy(number_of_expected_devices=1)
        self.assertEqual(2, ec.state)
        # this time it's all there and we move on
        sc.finalize_copy(number_of_expected_devices=None)

        self.assertEqual(1, ic.state)
        ic.copy_collections()
        self.assertEqual(2, ic.state)
        # this time it's all there and we move on
        ic.finalize_copy(number_of_expected_devices=None)
        self.assertEqual(3, ic.state)
        final_experiment_description = session_params.read_params(ic.remote_session_path)
        self.assertEqual(1, len(final_experiment_description['tasks']))
        self.assertEqual(set(final_experiment_description['devices']['cameras'].keys()), {'left'})
        self.assertEqual(set(final_experiment_description['sync'].keys()), {'nidq'})

    # Requires recent change to ibllib test fixture code supporting no probe ephys recording files
    @unittest.skipIf(version.parse(ibllib.__version__) < version.parse('2.39'), 'ibllib < 2.39')
    def test_ephys_no_probe(self):
        """Test copying a session at ephys rig when no probes were used (DAQ only)."""
        # First create a behavior session
        task_kwargs = copy.deepcopy(self.session_kwargs)
        task_kwargs['hardware_settings'].update(
            {
                'device_cameras': None,
                'MAIN_SYNC': False,  # this is quite important for ephys sessions
            }
        )
        session = _create_behavior_session(kwargs=task_kwargs, ntrials=50)
        folder_session_ephys = Path(self.td.name).joinpath('ephys', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])

        # Create an ephys acquisition
        n_probes = 0
        # SpikeGLX then saves these files into the session folder
        populate_raw_spikeglx(folder_session_ephys, model='3B', n_probes=n_probes)

        # Test the copiers
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual('.status_pending', sc.glob_file_remote_copy_status().suffix)
        self.assertEqual(1, sc.state)
        sc.copy_collections()
        self.assertEqual(2, sc.state)
        self.assertEqual('.status_complete', sc.glob_file_remote_copy_status().suffix)
        sc.copy_collections()
        self.assertEqual(2, sc.state)
        sc.finalize_copy(number_of_expected_devices=None)
        self.assertEqual(2, sc.state)  # here we still don't have all devices so we stay in state 2

        ec = EphysCopier(session_path=folder_session_ephys, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual(0, ec.state)
        ec.initialize_experiment()
        self.assertEqual(1, ec.state)
        self.assertIn('sync', ec.experiment_description)
        ec.copy_collections()
        self.assertEqual(2, ec.state)
        # this time it's all there and we move on
        ec.finalize_copy(number_of_expected_devices=None)
        self.assertEqual(3, ec.state)
        final_experiment_description = session_params.read_params(ec.remote_session_path)
        self.assertEqual(1, len(final_experiment_description['tasks']))
        self.assertEqual(set(final_experiment_description['sync'].keys()), {'nidq'})

    def test_copy_snapshots(self):
        """Test copy of snapshots folder(s)."""
        # Create without task data
        session = _create_behavior_session(kwargs=self.session_kwargs)
        snapshots = session.paths.SESSION_FOLDER.joinpath('snapshots')

        # Should log and return True when local snapshots folder does not exist
        sc = SessionCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        with self.assertLogs('iblrig.transfer_experiments', 'DEBUG'):
            self.assertTrue(sc.copy_snapshots())

        # Create some files in local folder 1
        snapshots.mkdir(parents=True)
        # Should log and return True when local snapshots folder is empty
        with self.assertLogs('iblrig.transfer_experiments', 'DEBUG'):
            self.assertTrue(sc.copy_snapshots())
        for i in range(2):
            file = snapshots.joinpath(f'snapshot_{i:02}.png')
            with open(file, 'wb') as fp:
                fp.write(i.to_bytes(24, byteorder='big', signed=False))
        # Create some subdirs to check copy is recursive
        snapshots.joinpath('_old').mkdir()
        file = snapshots.joinpath('_old', 'snapshot_0.jpg')
        with open(file, 'wb') as fp:  # numbers are garbage just for testing hash checks
            fp.write((42).to_bytes(24, byteorder='big', signed=False))

        # Should copy files recursively
        self.assertTrue(sc.copy_snapshots())
        remote_snapshots = sc.remote_session_path.joinpath('snapshots')
        self.assertTrue(remote_snapshots.exists())
        expected = ['snapshot_00.png', 'snapshot_01.png', '_old/snapshot_0.jpg']
        copied = [x.relative_to(remote_snapshots).as_posix() for x in filter(Path.is_file, remote_snapshots.rglob('*'))]
        self.assertCountEqual(expected, copied)

        # Create a file in local folder 2
        folder_session_video = Path(self.td.name).joinpath('video', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
        video_snapshots = folder_session_video.joinpath('snapshots')
        video_snapshots.mkdir(parents=True)
        # Another unique filename to copy
        file = snapshots.joinpath(expected[0]).rename(video_snapshots.joinpath(expected[0]).with_suffix('.jpeg'))

        # Should copy the file without removing those already in the remote snapshots folder
        sc = SessionCopier(session_path=folder_session_video, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertTrue(sc.copy_snapshots())
        expected.append(file.name)
        copied = [x.relative_to(remote_snapshots).as_posix() for x in filter(Path.is_file, remote_snapshots.rglob('*'))]
        self.assertCountEqual(expected, copied)

        # Create another local snapshots file in a subdir
        video_snapshots.joinpath('_old').mkdir()
        file.rename(video_snapshots.joinpath('_old', file.name))
        self.assertTrue(sc.copy_snapshots())
        # Calling copy method again should cause error log as remote duplicates found
        with self.assertLogs('iblrig.transfer_experiments', 'ERROR') as lg:
            self.assertFalse(sc.copy_snapshots())
        self.assertTrue(lg.output[-1].endswith('_old/snapshot_00.jpeg'))


class TestBuildGlobPattern(unittest.TestCase):
    """Test iblrig.commands._build_glob_pattern function."""

    def test_build_glob_pattern(self):
        self.assertEqual('*/*-*-*/*/transfer_me.flag', iblrig.commands._build_glob_pattern())
        glob_pattern = iblrig.commands._build_glob_pattern(subject='SP*', date='2023-*', number='001')
        self.assertEqual('SP*/2023-*/001/transfer_me.flag', glob_pattern)
        glob_pattern = iblrig.commands._build_glob_pattern(flag_file='flag.file', subject='foo')
        self.assertEqual('foo/*-*-*/*/flag.file', glob_pattern)
        glob_pattern = iblrig.commands._build_glob_pattern(flag_file='flag.file', glob_pattern='foo/bar/baz.*')
        self.assertEqual('foo/bar/baz.*', glob_pattern)
