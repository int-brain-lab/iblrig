import logging
import random
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import iblrig.commands
import iblrig.path_helper
import iblrig.raw_data_loaders
from ibllib.io import session_params
from ibllib.tests.fixtures.utils import populate_raw_spikeglx
from iblrig.path_helper import HardwareSettings, load_pydantic_yaml
from iblrig.test.base import TASK_KWARGS
from iblrig.transfer_experiments import BehaviorCopier, EphysCopier, VideoCopier
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session


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
    for name in ('iblrig', 'pybpodapi'):
        h = next(h for h in logging.getLogger(name).handlers if h.name == f'{name}_file')
        h.close()
        logging.getLogger(name).removeHandler(h)
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
    # we need to remove the file logging otherwise the hash of the logfile will not match
    session._remove_file_loggers()
    return session


class TestIntegrationTransferExperiments(unittest.TestCase):
    """This test emulates the `transfer_data` command as run on the rig."""

    def setUp(self):
        self.iblrig_settings = iblrig.path_helper.load_pydantic_yaml(
            iblrig.path_helper.RigSettings, 'iblrig_settings_template.yaml'
        )
        self.hardware_settings = iblrig.path_helper.load_pydantic_yaml(
            iblrig.path_helper.HardwareSettings, 'hardware_settings_template.yaml'
        )
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

    def side_effect(self, *args, filename=None, **kwargs):
        if filename.name.endswith('hardware_settings.yaml'):
            return self.hardware_settings
        else:
            return self.iblrig_settings

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
            with mock.patch('iblrig.path_helper._load_settings_yaml') as mocker:
                mocker.side_effect = self.side_effect
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

        with mock.patch('iblrig.path_helper._load_settings_yaml') as mocker:
            mocker.side_effect = self.side_effect
            iblrig.commands.transfer_data(tag='behavior')
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        self.assertEqual(sc.state, 3)

    def test_behavior_do_not_copy_dummy_sessions(self):
        """
        Here we test the case when an aborted session or a session with less than 42 trials attempts to be copied
        The expected behaviour is for the session folder on the remote session to be removed
        :return:
        """
        for ntrials in [41, None]:
            session = _create_behavior_session(ntrials=ntrials, kwargs=self.session_kwargs)
            session.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
            with mock.patch('iblrig.path_helper._load_settings_yaml') as mocker:
                mocker.side_effect = self.side_effect
                iblrig.commands.transfer_data(
                    local_path=session.iblrig_settings['iblrig_local_data_path'],
                    remote_path=session.iblrig_settings['iblrig_remote_data_path'],
                    tag='behavior',
                )
            sc = BehaviorCopier(
                session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER
            )
            self.assertFalse(sc.remote_session_path.exists())

    def test_behavior_copy(self):
        """
        Unlike the integration test, the sessions here are made from scratch using an actual instantiated session
        :return:
        """
        session = _create_behavior_session(kwargs=self.session_kwargs)
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
        assert sc.state == 1
        sc.copy_collections()
        assert sc.state == 2
        sc.finalize_copy(number_of_expected_devices=1)
        assert sc.state == 3  # this time it's all there and we move on

    def test_behavior_ephys_video_copy(self):
        """
        Unlike the integration test, the sessions here are made from scratch using an actual instantiated session
        :return:
        """
        with tempfile.TemporaryDirectory() as td:
            """
            First create a behavior session
            """
            task_kwargs = copy.deepcopy(self.session_kwargs)
            task_kwargs['hardware_settings'].update(
                {
                    'device_cameras': None,
                    'MAIN_SYNC': False,  # this is quite important for ephys sessions
                }
            )
            session = Session(**task_kwargs)
            session.create_session()
            session._remove_file_loggers()
            # SESSION_RAW_DATA_FOLDER is the one that gets copied
            folder_session_video = Path(td).joinpath('video', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
            folder_session_ephys = Path(td).joinpath('ephys', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])

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

        # Test the copiers
        sc = BehaviorCopier(session_path=session.paths.SESSION_FOLDER, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
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
        hws = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        vc.create_video_stub(hws['device_cameras']['default'])
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
        self.assertEqual(set(final_experiment_description['devices']['cameras'].keys()), {'left'})
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
