"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, i.e. on any computer.
The start() methods of those mixins require the hardware to be connected.

"""

import argparse
import tempfile
import unittest
from pathlib import Path
from threading import Timer
from unittest import mock

import numpy as np
import yaml

import ibllib.io.session_params as ses_params
from ibllib.io.session_params import read_params
from iblrig.base_choice_world import BiasedChoiceWorldSession, ChoiceWorldSession
from iblrig.base_tasks import BaseSession, BonsaiRecordingMixin
from iblrig.misc import _post_parse_arguments, get_task_argument_parser
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.test.base import PATH_FIXTURES, BaseTestCases
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld import task as tcw_task


class EmptyHardwareSession(BaseSession):
    protocol_name = 'empty_hardware_session_for_testing'

    def __init__(self, *args, **kwargs):
        self.extractor_tasks = ['Tutu', 'Tata']
        super().__init__(*args, **kwargs)

    def start_hardware(self):
        pass

    def _run(self):
        pass


class TestHierarchicalParameters(BaseTestCases.CommonTestTask):
    def test_default_params(self):
        self.get_task_kwargs()
        sess = BiasedChoiceWorldSession(**self.task_kwargs)
        file_params = self.tmp.joinpath('params.yaml')
        with open(file_params, 'w+') as fp:
            yaml.safe_dump(data={'TITI': 1, 'REWARD_AMOUNT_UL': -2}, stream=fp)
        sess2 = BiasedChoiceWorldSession(task_parameter_file=file_params, **self.task_kwargs)
        assert len(sess2.task_params.keys()) == len(sess.task_params.keys()) + 1
        assert sess2.task_params['TITI'] == 1
        assert sess2.task_params['REWARD_AMOUNT_UL'] == -2


class TestExtractorTypes(BaseTestCases.CommonTestTask):
    """
    EmptyHardwareSession sepcifies the extractors in the __init__ method, and the extractors
    are reflected in the experiment description file
    """

    def test_overriden_extractor_types(self):
        self.get_task_kwargs(tmpdir=False)
        sess = EmptyHardwareSession(**self.task_kwargs)
        self.assertEqual(sess.experiment_description['tasks'][0][sess.protocol_name]['extractors'], ['Tutu', 'Tata'])


class TestExperimentDescription(unittest.TestCase):
    """
    Test creation of experiment description dictionary
    Note: another part of testing is done in test/base.py, where the specific extractor classes
    are passed on to the acquisition description and tested for each task.
    """

    def setUp(self) -> None:
        self.stub = {
            'version': '1.0.0',
            'tasks': [{'choiceWorld': {'collection': 'raw_behavior_data', 'sync_label': 'bpod'}}],
            'procedures': ['Imaging'],
            'projects': ['foo'],
            'devices': {'cameras': {'left': {'collection': 'raw_video_data', 'sync_label': 'audio'}}},
        }
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.stub_path = ses_params.write_params(tempdir.name, self.stub)

    def test_new_description(self):
        """Test creation of a brand new experiment description (no stub)."""
        hardware_settings = {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3',
            'device_bpod': {'FOO': 10, 'BAR': 20},
            'device_cameras': {'default': {'left': {'SYNC_LABEL': 'audio'}}},
        }
        description = BaseSession.make_experiment_description_dict(
            'choiceWorld', 'raw_behavior_data', procedures=['Imaging'], projects=['foo'], hardware_settings=hardware_settings
        )
        expected = {k: v for k, v in self.stub.items() if k != 'version'}
        self.assertDictEqual(expected, description)

        # Test sync
        hardware_settings['MAIN_SYNC'] = True
        description = BaseSession.make_experiment_description_dict(
            'choiceWorld', 'raw_behavior_data', hardware_settings=hardware_settings
        )
        expected = {'bpod': {'collection': 'raw_behavior_data', 'acquisition_software': 'pybpod', 'extension': '.jsonable'}}
        self.assertDictEqual(expected, description.get('sync', {}))

    def test_stub(self):
        """Test merging of experiment description with a stub"""
        hardware_settings = {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3',
            'device_bpod': {'FOO': 20, 'BAR': 30},
            'device_foo': {'one': {'BAR': 'baz'}},
        }
        description = BaseSession.make_experiment_description_dict(
            'passiveWorld', 'raw_task_data_00', projects=['foo', 'bar'], hardware_settings=hardware_settings, stub=self.stub_path
        )
        self.assertCountEqual(['Imaging'], description['procedures'])
        self.assertCountEqual(['bar', 'foo'], description['projects'])
        self.assertCountEqual(['cameras'], description.get('devices', {}).keys())
        expected = self.stub['tasks'] + [{'passiveWorld': {'collection': 'raw_task_data_00', 'sync_label': 'bpod'}}]
        self.assertCountEqual(expected, description.get('tasks', []))


class TestPathCreation(BaseTestCases.CommonTestTask):
    """Test creation of experiment description dictionary."""

    def setUp(self):
        self.get_task_kwargs()

    def test_create_chained_protocols(self):
        # creates a first task with no remote and main sync set to false
        self.task_kwargs['iblrig_settings']['iblrig_remote_data_path'] = False
        self.task_kwargs['hardware_settings']['MAIN_SYNC'] = False
        self.task = EmptyHardwareSession(**self.task_kwargs, task_parameter_file=ChoiceWorldSession.base_parameters_file)
        self.task.create_session()
        # append a new protocol to the current task
        second_task = EmptyHardwareSession(append=True, **self.task_kwargs)
        # unless the task has reached the create session stage, there is only one protocol in there
        self.assertEqual(set(d.name for d in self.task.paths.SESSION_FOLDER.iterdir() if d.is_dir()), {'raw_task_data_00'})
        # this will create and add to the acquisition description file
        second_task.create_session()
        self.assertEqual(
            set(d.name for d in self.task.paths.SESSION_FOLDER.iterdir() if d.is_dir()), {'raw_task_data_00', 'raw_task_data_01'}
        )
        description = read_params(second_task.paths['SESSION_FOLDER'])
        # we should also find the protocols in the acquisition description file
        protocols = set(p[EmptyHardwareSession.protocol_name]['collection'] for p in description['tasks'])
        self.assertEqual(protocols, {'raw_task_data_00', 'raw_task_data_01'})

    def test_create_session_with_remote(self):
        with tempfile.TemporaryDirectory() as td:
            self.task_kwargs['iblrig_settings']['iblrig_remote_data_path'] = Path(td)
            task = EmptyHardwareSession(**self.task_kwargs)
            task.create_session()
            # when we create the session, the local session folder is created with the acquisition description file
            description_file_local = next(task.paths['SESSION_FOLDER'].glob('_ibl_experiment.description*.yaml'), None)
            remote_session_path = task.paths['REMOTE_SUBJECT_FOLDER'].joinpath(
                task.paths['SESSION_FOLDER'].relative_to(task.paths['LOCAL_SUBJECT_FOLDER'])
            )
            # there is also the acquisition description stub in the remote folder
            description_file_remote = next(remote_session_path.joinpath('_devices').glob('*.yaml'), None)
            assert description_file_local is not None
            assert description_file_remote is not None

    def test_create_session_without_remote(self):
        self.task_kwargs['iblrig_settings']['iblrig_remote_data_path'] = None
        self.task = EmptyHardwareSession(**self.task_kwargs)
        self.task.create_session()
        # when we create the session, the local session folder is created with the acquisition description file
        description_file_local = next(self.task.paths['SESSION_FOLDER'].glob('_ibl_experiment.description*.yaml'), None)
        assert description_file_local is not None

    def test_create_session_unavailable_remote(self):
        self.task_kwargs['iblrig_settings']['iblrig_remote_data_path'] = '/path/that/doesnt/exist'
        self.task = EmptyHardwareSession(**self.task_kwargs)
        self.task.create_session()
        # when we create the session, the local session folder is created with the acquisition description file
        description_file_local = next(self.task.paths['SESSION_FOLDER'].glob('_ibl_experiment.description*.yaml'), None)
        assert description_file_local is not None


class TestTaskArguments(unittest.TestCase):
    @staticmethod
    def _parse_local(args, parents=None):
        parser = get_task_argument_parser(parents=parents)
        kwargs = vars(parser.parse_args(args))
        kwargs = _post_parse_arguments(**kwargs)
        return kwargs

    def test_arg_parser_simple(self):
        kwargs = self._parse_local(args=['--subject', 'toto', '-u', 'john.doe'])
        self.assertTrue(kwargs['interactive'])
        self.assertEqual(kwargs['subject'], 'toto')
        projects = ['titi', 'tata']
        procedures = ['tata', 'titi']
        kwargs = self._parse_local(
            args=['--subject', 'toto', '-u', 'john.doe', '--projects', *projects, '--procedures', *procedures]
        )
        self.assertEqual(set(kwargs['projects']), set(projects))
        self.assertEqual(set(kwargs['procedures']), set(procedures))

    def test_arg_parser_user(self):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--training_phase', option_strings=['--training_phase'], dest='training_phase', default=0, type=int)
        kwargs = self._parse_local(args=['--subject', 'toto', '--training_phase', '4'], parents=[parser])
        self.assertTrue(kwargs['interactive'])
        self.assertEqual(kwargs['subject'], 'toto')
        self.assertEqual(kwargs['training_phase'], 4)


class TestHardwareSettings(unittest.TestCase):
    def test_get_left_camera_workflow(self):
        hws = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        config = hws['device_cameras']['default']
        self.assertIsNotNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file(config, 'recording'))
        self.assertIsNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file(None, 'recording'))
        self.assertRaises(KeyError, BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file, {}, 'recording')


class TestRun(BaseTestCases.CommonTestTask):
    """Test BaseSession.run method and append kwarg."""

    def setUp(self):
        self.get_task_kwargs()
        self.task_kwargs['hardware_settings']['MAIN_SYNC'] = False
        self.task_kwargs['interactive'] = True
        self.task_kwargs['task_parameter_file'] = ChoiceWorldSession.base_parameters_file

    @mock.patch('iblrig.base_tasks.graph.numinput', side_effect=(23.5, 20, 35))
    def test_dialogs(self, input_mock):
        """Test that weighing dialog used only on first of chained protocols."""
        self.task_kwargs.pop('subject_weight_grams')
        self.task = EmptyHardwareSession(**self.task_kwargs)
        # Check that weighing GUI created
        self.task.run()
        input_mock.assert_called()
        self.assertEqual(23.5, self.task.session_info['SUBJECT_WEIGHT'])
        self.assertEqual(20, self.task.session_info['POOP_COUNT'])

        # Append a new protocol to the current task. Weighting GUI should not be instantiated
        input_mock.reset_mock()
        second_task = EmptyHardwareSession(append=True, **self.task_kwargs)
        second_task.run()
        input_mock.assert_called_once()
        self.assertIsNone(second_task.session_info['SUBJECT_WEIGHT'])
        self.assertEqual(35, second_task.session_info['POOP_COUNT'])


class _PauseChoiceWorldSession(ChoiceWorldSession):
    protocol_name = 'pause_session_for_testing'
    pause_trial = None  # trial on which to simulate pause message
    stop_trial = None  # trial on which to stimulate stop message

    def start_hardware(self):
        pass

    def _delete_pause_flag(self):
        if self.trial_num == self.pause_trial and self.pause_flag.exists():
            self.pause_flag.unlink()

    @property
    def pause_flag(self):
        return self.paths.SESSION_FOLDER.joinpath('.pause')

    def run_state_machine(self, _):
        # simulate pause button press by user
        if self.pause_trial is not None and self.pause_trial == self.trial_num:
            self.pause_flag.touch()
            Timer(0.1, self._delete_pause_flag).start()
        if self.stop_trial is not None and self.stop_trial == self.trial_num:
            self.pause_flag.with_name('.stop').touch()

    def mock(self, **kwargs):
        super().mock(**kwargs)
        # restore run_state_machine method (mock replaces this with a lambda)
        self.bpod.run_state_machine = self.run_state_machine

    def next_trial(self):
        self.trial_num += 1
        self.draw_next_trial_info()


class TestBaseChoiceWorld(BaseTestCases.CommonTestTask):
    """Test base_choice_world.ChoiceWorldSession class."""

    def setUp(self):
        self.get_task_kwargs()

    def test_pause_and_stop(self):
        """Test choice world pause and stop flag behaviour in _run method."""
        # Instantiate special task that touches pause and stop flags on specified trials
        self.task = _PauseChoiceWorldSession(**self.task_kwargs)
        self.task.mock(file_jsonable_fixture=PATH_FIXTURES.joinpath('task_data_short.jsonable'))
        self.task.task_params.NTRIALS = 10  # run for 10 trials max
        self.task.pause_trial = 3  # simulate pause on 3rd trial
        self.task.stop_trial = 5  # simulate stop on 5th trial

        with self.assertLogs('iblrig.base_choice_world', 20) as lg:
            self.task.run()

        # Check pause and stop are correctly logged
        self.assertRegex(lg.records[-1].getMessage(), r'Stopping [\w\s]+ ' + str(self.task.stop_trial))
        pause_log = next((x for x in lg.records if x.getMessage().startswith('Pausing')), None)
        self.assertIsNotNone(pause_log)
        self.assertRegex(pause_log.getMessage(), r'Pausing [\w\s]+ ' + str(self.task.pause_trial))

        # Check we stopped after the expected trial
        self.assertEqual(self.task.session_info.NTRIALS, self.task.stop_trial + 1, 'failed to stop early')
        stop_flag = self.task.paths.SESSION_FOLDER.joinpath('.stop')
        self.assertFalse(stop_flag.exists(), 'failed to remove stop flag')
        # Check trials updated with pause duration
        (idx,) = np.where(self.task.trials_table['pause_duration'][: self.task.task_params.NTRIALS] > 0)
        self.assertCountEqual(idx, [self.task.pause_trial], 'failed to correctly update pause_duration field')


class TestClassMethods(unittest.TestCase):
    def test_get_task_file(self):
        task_file = tcw_task.Session.get_task_file()
        self.assertEqual(task_file, Path(tcw_task.__file__))

    def test_get_task_directory(self):
        task_dir = tcw_task.Session.get_task_directory()
        self.assertEqual(task_dir, Path(tcw_task.__file__).parent)

    def test_read_task_parameter_files(self):
        task_params = tcw_task.Session.read_task_parameter_files()
        self.assertTrue('AG_INIT_VALUE' in task_params)  # from training choice world
        self.assertTrue('NTRIALS' in task_params)  # from base parameters
