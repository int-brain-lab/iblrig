"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.

"""
import argparse
import copy
from pathlib import Path
import unittest
import tempfile

import yaml
import ibllib.io.session_params as ses_params

from iblrig.test.base import TASK_KWARGS
from iblrig.base_tasks import (SoundMixin, RotaryEncoderMixin, BaseSession, BpodMixin,
                               ValveMixin, Frame2TTLMixin)
from iblrig.base_choice_world import BiasedChoiceWorldSession, ChoiceWorldSession
from ibllib.io.session_params import read_params
from iblrig.misc import _get_task_argument_parser, _post_parse_arguments


class EmptyHardwareSession(BaseSession):
    protocol_name = 'empty_hardware_session_for_testing'

    def start_hardware(self):
        pass

    def _run(self):
        pass


class TestHierarchicalParameters(unittest.TestCase):

    def test_default_params(self):
        sess = BiasedChoiceWorldSession(**TASK_KWARGS)
        with tempfile.TemporaryDirectory() as td:
            file_params = Path(td).joinpath('params.yaml')
            with open(file_params, 'w+') as fp:
                yaml.safe_dump(data={'TITI': 1, 'REWARD_AMOUNT_UL': -2}, stream=fp)
            sess2 = BiasedChoiceWorldSession(task_parameter_file=file_params, **TASK_KWARGS)
        assert len(sess2.task_params.keys()) == len(sess.task_params.keys()) + 1
        assert sess2.task_params['TITI'] == 1
        assert sess2.task_params['REWARD_AMOUNT_UL'] == -2


class TestHardwareMixins(unittest.TestCase):
    def setUp(self):
        task_settings_file = ChoiceWorldSession.base_parameters_file
        self.session = EmptyHardwareSession(task_parameter_file=task_settings_file, **TASK_KWARGS)

    def test_rotary_encoder_mixin(self):
        """
        Instantiates a bare session with the rotary encoder mixin
        """
        session = self.session
        RotaryEncoderMixin.init_mixin_rotary_encoder(session)
        assert session.device_rotary_encoder.ENCODER_EVENTS == [
            'RotaryEncoder1_1', 'RotaryEncoder1_2', 'RotaryEncoder1_3', 'RotaryEncoder1_4']
        assert session.device_rotary_encoder.THRESHOLD_EVENTS == {
            -35: 'RotaryEncoder1_1',
            35: 'RotaryEncoder1_2',
            -2: 'RotaryEncoder1_3',
            2: 'RotaryEncoder1_4'
        }
        with self.assertRaises(ValueError):
            RotaryEncoderMixin.start_mixin_rotary_encoder(session)

    def test_frame2ttl_mixin(self):
        """
        Instantiates a bare session with the frame2ttl mixin
        """
        session = self.session
        Frame2TTLMixin.init_mixin_frame2ttl(session)
        with self.assertRaises(ValueError):
            Frame2TTLMixin.start_mixin_frame2ttl(session)

    def test_sound_card_mixin(self):
        """
        Instantiates a bare session with the sound card mixin
        """
        session = self.session
        SoundMixin.init_mixin_sound(session)
        assert session.sound.GO_TONE is not None

    def test_bpod_mixin(self):
        session = self.session
        BpodMixin.init_mixin_bpod(session)
        assert hasattr(session, 'bpod')
        with self.assertRaises(ValueError):
            BpodMixin.start_mixin_bpod(session)

    def test_valve_mixin(self):
        session = self.session
        ValveMixin.init_mixin_valve(session)
        # assert session.valve.compute < 1
        assert not session.valve.is_calibrated


class TestExperimentDescription(unittest.TestCase):
    """
    Test creation of experiment description dictionary
    Note: another part of testing is done in test/base.py, where the specific extractor classes
    are passed on to the acquisition description and tested for each task.
    """

    def setUp(self) -> None:
        self.stub = {
            'version': '1.0.0',
            'tasks': [{'choiceWorld': {
                'collection': 'raw_behavior_data', 'sync_label': 'bpod'}}],
            'procedures': ['Imaging'],
            'projects': ['foo'],
            'devices': {
                'cameras': {'left': {'collection': 'raw_video_data', 'sync_label': 'audio'}}}
        }
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.stub_path = ses_params.write_params(tempdir.name, self.stub)

    def test_new_description(self):
        """Test creation of a brand new experiment description (no stub)"""
        hardware_settings = {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3',
            'device_bpod': {'FOO': 10, 'BAR': 20},
            'device_cameras': {'left': {'BAZ': 0}}
        }
        description = BaseSession.make_experiment_description_dict(
            'choiceWorld', 'raw_behavior_data', procedures=['Imaging'], projects=['foo'], hardware_settings=hardware_settings)
        expected = {k: v for k, v in self.stub.items() if k != 'version'}
        self.assertDictEqual(expected, description)

        # Test sync
        hardware_settings['MAIN_SYNC'] = True
        description = BaseSession.make_experiment_description_dict(
            'choiceWorld', 'raw_behavior_data', hardware_settings=hardware_settings)
        expected = {'bpod': {'collection': 'raw_behavior_data', 'acquisition_software': 'pybpod', 'extension': '.jsonable'}}
        self.assertDictEqual(expected, description.get('sync', {}))

    def test_stub(self):
        """Test merging of experiment description with a stub"""
        hardware_settings = {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3',
            'device_bpod': {'FOO': 20, 'BAR': 30},
            'device_foo': {'one': {'BAR': 'baz'}}
        }
        description = BaseSession.make_experiment_description_dict(
            'passiveWorld', 'raw_task_data_00', projects=['foo', 'bar'], hardware_settings=hardware_settings, stub=self.stub_path)
        self.assertCountEqual(['Imaging'], description['procedures'])
        self.assertCountEqual(['bar', 'foo'], description['projects'])
        self.assertCountEqual(['cameras'], description.get('devices', {}).keys())
        expected = self.stub['tasks'] + [{'passiveWorld': {'collection': 'raw_task_data_00', 'sync_label': 'bpod'}}]
        self.assertCountEqual(expected, description.get('tasks', []))


class TestPathCreation(unittest.TestCase):
    """Test creation of experiment description dictionary."""

    def test_create_chained_protocols(self):
        # creates a first task
        task_kwargs = copy.deepcopy(TASK_KWARGS)
        task_kwargs['hardware_settings']['MAIN_SYNC'] = False
        first_task = EmptyHardwareSession(iblrig_settings={'iblrig_remote_data_path': False},
                                          **task_kwargs, task_parameter_file=ChoiceWorldSession.base_parameters_file)
        first_task.create_session()
        # append a new protocol the the current task
        second_task = EmptyHardwareSession(append=True, iblrig_settings={'iblrig_remote_data_path': False}, **task_kwargs)
        # unless the task has reached the create session stage, there is only one protocol in there
        self.assertEqual(set([d.name for d in first_task.paths.SESSION_FOLDER.iterdir() if d.is_dir()]),
                         set(['raw_task_data_00']))
        # this will create and add to the acquisition description file
        second_task.create_session()
        self.assertEqual(set([d.name for d in first_task.paths.SESSION_FOLDER.iterdir() if d.is_dir()]),
                         set(['raw_task_data_00', 'raw_task_data_01']))
        description = read_params(second_task.paths['SESSION_FOLDER'])
        # we should also find the protocols in the acquisition description file
        protocols = set([p[EmptyHardwareSession.protocol_name]['collection'] for p in description['tasks']])
        self.assertEqual(protocols, set(['raw_task_data_00', 'raw_task_data_01']))

    def test_create_session_with_remote(self):

        with tempfile.TemporaryDirectory() as td:
            task = EmptyHardwareSession(iblrig_settings={'iblrig_remote_data_path': Path(td)}, **TASK_KWARGS)
            task.create_session()
            # when we create the session, the local session folder is created with the acquisition description file
            description_file_local = next(task.paths['SESSION_FOLDER'].glob('_ibl_experiment.description*.yaml'), None)
            remote_session_path = task.paths['REMOTE_SUBJECT_FOLDER'].joinpath(
                task.paths['SESSION_FOLDER'].relative_to(task.paths['LOCAL_SUBJECT_FOLDER']))
            # there is also the acquisition description stub in the remote folder
            description_file_remote = next(remote_session_path.joinpath('_devices').glob('*.yaml'), None)
            assert description_file_local is not None
            assert description_file_remote is not None

    def test_create_session_without_remote(self):
        task = EmptyHardwareSession(iblrig_settings={'iblrig_remote_data_path': None}, **TASK_KWARGS)
        task.create_session()
        # when we create the session, the local session folder is created with the acquisition description file
        description_file_local = next(task.paths['SESSION_FOLDER'].glob('_ibl_experiment.description*.yaml'), None)
        assert description_file_local is not None

    def test_create_session_unavailable_remote(self):
        task = EmptyHardwareSession(iblrig_settings={'iblrig_remote_data_path': '/path/that/doesnt/exist'}, **TASK_KWARGS)
        task.create_session()
        # when we create the session, the local session folder is created with the acquisition description file
        description_file_local = next(task.paths['SESSION_FOLDER'].glob('_ibl_experiment.description*.yaml'), None)
        assert description_file_local is not None


class TestTaskArguments(unittest.TestCase):

    @staticmethod
    def _parse_local(args, parents=None):
        parser = _get_task_argument_parser(parents=parents)
        kwargs = vars(parser.parse_args(args))
        kwargs = _post_parse_arguments(**kwargs)
        return kwargs

    def test_arg_parser_simple(self):
        kwargs = self._parse_local(args=['--subject', 'toto', '-u', 'john.doe'])
        self.assertTrue(kwargs['interactive'])
        self.assertEqual(kwargs['subject'], 'toto')
        projects = ['titi', 'tata']
        procedures = ['tata', 'titi']
        kwargs = self._parse_local(args=['--subject', 'toto', '-u', 'john.doe', '--projects',
                                         *projects, '--procedures', *procedures])
        self.assertEqual(set(kwargs['projects']), set(projects))
        self.assertEqual(set(kwargs['procedures']), set(procedures))

    def test_arg_parser_user(self):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--training_phase', option_strings=['--training_phase'], dest='training_phase', default=0, type=int)
        kwargs = self._parse_local(args=['--subject', 'toto', '--training_phase', '4'], parents=[parser])
        self.assertTrue(kwargs['interactive'])
        self.assertEqual(kwargs['subject'], 'toto')
        self.assertEqual(kwargs['training_phase'], 4)
