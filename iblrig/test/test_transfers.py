import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from iblutil.util import Bunch

import iblrig.commands
import iblrig.raw_data_loaders
from ibllib.io import session_params
from iblrig.test.base import TASK_KWARGS
from iblrig.transfer_experiments import BehaviorCopier, EphysCopier, VideoCopier
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session


def _create_behavior_session(temp_dir, ntrials=None, hard_crash=False, **kwargs):
    """
    Creates a generic session in a tempdir. If ntrials is specified, create a jsonable file with ntrials
    and update the task settings
    :param temp_dir:
    :param ntrials:
    :param hard_crash: if True, simulates a hardcrash by not labeling the session end time and ntrials
    :return:
    """
    task_kwargs = {**TASK_KWARGS, **kwargs}
    iblrig_settings = {
        'iblrig_local_data_path': Path(temp_dir).joinpath('behavior'),
        'iblrig_remote_data_path': Path(temp_dir).joinpath('remote'),
        'ALYX_LAB': 'testlab',
    }
    session = Session(iblrig_settings=iblrig_settings, **task_kwargs)
    session.create_session()
    session.paths.SESSION_FOLDER.joinpath('raw_video_data').mkdir(parents=True)
    session.paths.SESSION_FOLDER.joinpath('raw_video_data', 'tutu.avi').touch()
    if ntrials is not None:
        with open(Path(__file__).parent.joinpath('fixtures', 'task_data_short.jsonable')) as fid:
            lines = fid.readlines()
        with open(Path(session.paths.DATA_FILE_PATH), 'w') as fid:
            for _ in range(ntrials):
                fid.write(random.choice(lines))
        if not hard_crash:
            session.session_info['NTRIALS'] = ntrials
            session.session_info['SESSION_END_TIME'] = session.session_info['SESSION_START_TIME']
            session.save_task_parameters_to_json_file()
    return session


class TestIntegrationTransferExperiments(unittest.TestCase):
    """This test emulates the `transfer_data` command as run on the rig."""

    def test_behavior_copy_complete_session(self):
        """
        Here there are 2 cases, one is about a complete session, the other is about a session that crashed
        but is still valid (i.e. more than 42 trials)
        In this case both sessions should end up on the remote path with a copy state of 3
        """
        self.assertRaises(ValueError, iblrig.commands.transfer_data)  # Should raise without tag
        for hard_crash in [False, True]:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                session = _create_behavior_session(td, ntrials=50, hard_crash=hard_crash)
                session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
                with mock.patch('iblrig.path_helper._load_settings_yaml', return_value=session.iblrig_settings):
                    iblrig.commands.transfer_data(tag='behavior')
                sc = BehaviorCopier(
                    session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
                )
                self.assertEqual(sc.state, 3)

        # Check that the settings file is used when no path passed
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            session = _create_behavior_session(td, ntrials=50, hard_crash=hard_crash)
            session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
            with mock.patch('iblrig.path_helper._load_settings_yaml', return_value=session.iblrig_settings):
                iblrig.commands.transfer_data(tag='behavior')
            sc = BehaviorCopier(
                session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
            )
            self.assertEqual(sc.state, 3)

    def test_behavior_do_not_copy_dummy_sessions(self):
        """
        Here we test the case when an aborted session or a session with less than 42 trials attempts to be copied
        The expected behaviour is for the session folder on the remote session to be removed
        :return:
        """
        for ntrials in [None, 41]:
            with tempfile.TemporaryDirectory() as td:
                session = _create_behavior_session(td, ntrials=ntrials)
                session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
                with mock.patch('iblrig.path_helper._load_settings_yaml', return_value=session.iblrig_settings):
                    iblrig.commands.transfer_data(tag='behavior')
                sc = BehaviorCopier(
                    session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
                )
                self.assertFalse(sc.remote_session_path.exists())


class TestGenericTransfer(unittest.TestCase):
    """This test emulates the `transfer_other_data` command as run at an acquisition PC."""

    def setUp(self):
        """Set up the copy fixtures and mock objects.

        This test simulates a 'timeline' main sync computer at the UCL mesoscope.
        """
        # Create a temporary directory
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.tmpdir = Path(tmpdir.name)

        # Create local and remote data locations
        self.local = self.tmpdir.joinpath('local', 'Subjects')
        self.remote = self.tmpdir.joinpath('remote', 'Subjects')
        self.local.mkdir(parents=True), self.remote.mkdir(parents=True)
        self.session = 'test/2023-12-01/001'

        # Mock settings file
        self.settings = Bunch({
            # Standard settings
            'iblrig_local_data_path': str(self.local),
            'iblrig_local_subjects_path': str(self.local),
            'iblrig_remote_data_path': str(self.remote),
            'iblrig_remote_subjects_path': str(self.remote),
            'ALYX_LAB': 'cortexlab',
            # Hardware settings
            'RIG_NAME': 'mesoscope_timeline',
            'MAIN_SYNC': True,
            'VERSION': '1.0.0'
        })
        self.settings_mock = mock.patch('iblrig.path_helper._load_settings_yaml', return_value=self.settings)
        self.settings_mock.start()
        self.addCleanup(self.settings_mock.stop)

        # Write remote files.
        (folder := self.remote.joinpath(self.session, '_devices')).mkdir(parents=True)
        folder.joinpath('2023-12-01_1_test@behavior.status_pending').touch()
        with open(folder / '2023-12-01_1_test@timeline.yaml', 'w') as fp:
            text = """
sync:
  nidq:
    acquisition_software: timeline
    collection: raw_sync_data
    extension: npy
version: 1.0.0
            """
            fp.write(text)

        # Write 'local' data
        folder = self.local.joinpath(self.session).parent.joinpath('1')
        folder.joinpath('raw_sync_data').mkdir(parents=True)
        timeline_files = ('_timeline_DAQdata.meta.json', '_timeline_DAQdata.raw.npy',
                          '_timeline_DAQdata.timestamps.npy', '_timeline_softwareEvents.log.htsv')
        for file in timeline_files:
            folder.joinpath('raw_sync_data', file).touch()
        src = self.remote.joinpath(self.session, '_devices', '2023-12-01_1_test@timeline.yaml')
        shutil.copy(src, folder / '_ibl_experiment.description_timeline.yaml')
        folder.joinpath('transfer_me.flag').touch()

    def test_copy_complete_session(self):
        """Tests the copy of a session using the SessionCopier base class with a specific tag."""
        copiers = iblrig.commands.transfer_data(tag='timeline', subject='foo')
        self.assertEqual(0, len(copiers))
        copiers = iblrig.commands.transfer_data(tag='timeline')
        self.assertEqual(1, len(copiers))
        self.assertTrue(self.remote.joinpath(self.session, 'raw_sync_data').exists())
        copied_files = list(self.remote.joinpath(self.session, 'raw_sync_data').iterdir())
        self.assertEqual(len(copied_files), 4, 'failed to copy all sync files')
        self.assertIsNone(next(self.local.rglob('transfer_me.flag'), None), 'failed to remove flag file')


class TestUnitTransferExperiments(unittest.TestCase):
    """
    UnitTest the BehaviorCopier, VideoCopier and EphysCopier classes and methods.

    Unlike the integration test, the sessions here are made from scratch using an actual instantiated session.
    """
    def setUp(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.tmpdir = Path(tmpdir.name)

    def test_behavior_dud_copy(self):
        """This tests the case where a dud session is copied.

        No task data is found so the remote session should be removed and the state should change
        from 1 to 0.
        """
        session = _create_behavior_session(self.tmpdir)
        sc = BehaviorCopier(
            session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
        )
        self.assertEqual(1, sc.state, 'expect remote stub file to return pending status')
        self.assertFalse(sc.copy_collections(), 'should fail as task data does not exist')
        self.assertEqual(0, sc.state, 'expect absent stub file to return unregistered status')
        self.assertFalse(sc.remote_session_path.exists())

    def test_behavior_ephys_video_copy(self):
        # Create a behavior session
        # For ephys sessions the behaviour MAIN_SYNC value must be False
        task_kwargs = {'hardware_settings': {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3', 'device_cameras': None, 'MAIN_SYNC': False
        }}
        session = _create_behavior_session(self.tmpdir, ntrials=50, hard_crash=False, **task_kwargs)
        # SESSION_RAW_DATA_FOLDER is the one that gets copied
        folder_session_video = self.tmpdir.joinpath('video', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
        folder_session_ephys = self.tmpdir.joinpath('ephys', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])

        # Create an ephys acquisition
        for i in range(2):
            pname = f'_spikeglx_ephysData_g0_t0.imec{str(i)}'
            folder_probe = folder_session_ephys.joinpath('raw_ephys_data', '_spikeglx_ephysData_g0', pname)
            folder_probe.mkdir(parents=True)
            for suffix in ['.ap.meta', '.lf.meta', '.ap.bin', '.lf.bin']:
                folder_probe.joinpath(f'{pname}{suffix}').touch()
        folder_session_ephys.joinpath(
            'raw_ephys_data', '_spikeglx_ephysData_g0', '_spikeglx_ephysData_g0_t0.imec0.nidq.bin'
        ).touch()
        folder_session_ephys.joinpath(
            'raw_ephys_data', '_spikeglx_ephysData_g0', '_spikeglx_ephysData_g0_t0.imec0.nidq.meta'
        ).touch()

        # Create a video acquisition
        folder_session_video.joinpath('raw_video_data').mkdir(parents=True)
        for vname in ['body', 'left', 'right']:
            folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.frameData.bin').touch()
            folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.raw.avi').touch()

        # Test the copiers
        sc = BehaviorCopier(
            session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
        )
        self.assertEqual('.status_pending', sc.glob_file_remote_copy_status().suffix)
        self.assertEqual(1, sc.state)
        sc.copy_collections()
        self.assertEqual(2, sc.state)
        self.assertEqual('.status_complete', sc.glob_file_remote_copy_status().suffix)
        sc.copy_collections()
        self.assertEqual(2, sc.state)
        sc.finalize_copy(number_of_expected_devices=3)
        self.assertEqual(2, sc.state)  # here we still don't have all devices so we stay in state 2

        vc = VideoCopier(session_path=folder_session_video, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        vc.create_video_stub()
        self.assertEqual(0, vc.state)
        vc.initialize_experiment()
        self.assertEqual(1, vc.state)
        vc.copy_collections()
        self.assertEqual(2, vc.state)
        sc.finalize_copy(number_of_expected_devices=3)
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
        sc.finalize_copy(number_of_expected_devices=3)
        self.assertEqual(3, sc.state)
        final_experiment_description = session_params.read_params(sc.remote_session_path)
        self.assertEqual(1, len(final_experiment_description['tasks']))
        self.assertEqual(set(final_experiment_description['devices']['cameras'].keys()), {'body', 'left', 'right'})
        self.assertEqual(set(final_experiment_description['sync'].keys()), {'nidq'})


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
