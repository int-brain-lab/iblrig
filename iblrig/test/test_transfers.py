import copy
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import iblrig.commands
import iblrig.raw_data_loaders
from ibllib.io import session_params
from iblrig.test.base import TASK_KWARGS
from iblrig.transfer_experiments import BehaviorCopier, EphysCopier, VideoCopier
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session


def _create_behavior_session(temp_dir, ntrials=None, hard_crash=False):
    """
    Creates a generic session in a tempdir. If ntrials is specified, create a jsonable file with ntrials
    and update the task settings
    :param temp_dir:
    :param ntrials:
    :param hard_crash: if True, simulates a hardcrash by not labeling the session end time and ntrials
    :return:
    """
    iblrig_settings = {
        'iblrig_local_data_path': Path(temp_dir).joinpath('behavior'),
        'iblrig_remote_data_path': Path(temp_dir).joinpath('remote'),
        'ALYX_LAB': 'testlab',
    }
    session = Session(iblrig_settings=iblrig_settings, **TASK_KWARGS)
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
    """
    This test emulates the `transfer_data` command as run on the rig.
    """

    def test_behavior_copy_complete_session(self):
        """
        Here there are 2 cases, one is about a complete session, the other is about a session that crashed
        but is still valid (ie. more than 42 trials)
        In this case both sessions should end up on the remote path with a copy state of 3
        """
        for hard_crash in [False, True]:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                session = _create_behavior_session(td, ntrials=50, hard_crash=hard_crash)
                session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
                with mock.patch('iblrig.path_helper.load_settings_yaml', return_value=session.iblrig_settings):
                    iblrig.commands.transfer_data()
                sc = BehaviorCopier(
                    session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
                )
                self.assertEqual(sc.state, 3)

        # Check that the settings file is used when no path passed
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            session = _create_behavior_session(td, ntrials=50, hard_crash=hard_crash)
            session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
            with mock.patch('iblrig.path_helper.load_settings_yaml', return_value=session.iblrig_settings):
                iblrig.commands.transfer_data()
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
                with mock.patch('iblrig.path_helper.load_settings_yaml', return_value=session.iblrig_settings):
                    iblrig.commands.transfer_data()
                sc = BehaviorCopier(
                    session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
                )
                self.assertFalse(sc.remote_session_path.exists())


class TestUnitTransferExperiments(unittest.TestCase):
    """
    UnitTest the BehaviorCopier, VideoCopier and EphysCopier classes and methods
    Unlike the integration test, the sessions here are made from scratch using an actual instantiated session
    """

    def test_behavior_copy(self):
        with tempfile.TemporaryDirectory() as td:
            session = _create_behavior_session(td)
            sc = BehaviorCopier(
                session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
            )
            assert sc.state == 1
            sc.copy_collections()
            assert sc.state == 2
            sc.finalize_copy(number_of_expected_devices=1)
            assert sc.state == 3  # this time it's all there and we move on

    def test_behavior_ephys_video_copy(self):
        with tempfile.TemporaryDirectory() as td:
            """
            First create a behavior session
            """
            iblrig_settings = {
                'iblrig_local_data_path': Path(td).joinpath('behavior'),
                'iblrig_remote_data_path': Path(td).joinpath('remote'),
            }

            task_kwargs = copy.deepcopy(TASK_KWARGS)
            task_kwargs['hardware_settings'].update(
                {
                    'device_cameras': None,
                    'MAIN_SYNC': False,  # this is quite important for ephys sessions
                }
            )
            session = Session(iblrig_settings=iblrig_settings, **task_kwargs)
            session.create_session()
            # SESSION_RAW_DATA_FOLDER is the one that gets copied
            folder_session_video = Path(td).joinpath('video', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
            folder_session_ephys = Path(td).joinpath('ephys', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])

            """
            Create an ephys acquisition
            """
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
            """
            Create a video acquisition
            """
            folder_session_video.joinpath('raw_video_data').mkdir(parents=True)
            for vname in ['body', 'left', 'right']:
                folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.frameData.bin').touch()
                folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.raw.avi').touch()
            """
            Test the copiers
            """
            sc = BehaviorCopier(
                session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
            )
            assert sc.glob_file_remote_copy_status().suffix == '.status_pending'
            assert sc.state == 1
            sc.copy_collections()
            assert sc.state == 2
            assert sc.glob_file_remote_copy_status().suffix == '.status_complete'
            sc.copy_collections()
            assert sc.state == 2
            sc.finalize_copy(number_of_expected_devices=3)
            assert sc.state == 2  # here we still don't have all devides so this won't cut it and we stay in state 2

            vc = VideoCopier(session_path=folder_session_video, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
            vc.create_video_stub()
            assert vc.state == 0
            vc.initialize_experiment()
            assert vc.state == 1
            vc.copy_collections()
            assert vc.state == 2
            sc.finalize_copy(number_of_expected_devices=3)
            assert sc.state == 2  # here we still don't have all devides so this won't cut it and we stay in state 2

            ec = EphysCopier(session_path=folder_session_ephys, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
            assert ec.state == 0
            ec.initialize_experiment()
            assert ec.state == 1
            assert 'sync' in ec.experiment_description
            ec.copy_collections()
            assert ec.state == 2
            # here it is a bit tricky; we want to safeguard finalizing the copy when the sync is different than bpod
            # so in this case, we expect the status to stay at 2 and a warning to be thrown
            sc.finalize_copy(number_of_expected_devices=1)
            assert ec.state == 2
            # this time it's all there and we move on
            sc.finalize_copy(number_of_expected_devices=3)
            assert sc.state == 3
            final_experiment_description = session_params.read_params(sc.remote_session_path)
            assert len(final_experiment_description['tasks']) == 1
            assert set(final_experiment_description['devices']['cameras'].keys()) == set(['body', 'left', 'right'])
            assert set(final_experiment_description['sync'].keys()) == set(['nidq'])
