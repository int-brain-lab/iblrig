"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.

"""
from pathlib import Path
import unittest
import tempfile

import yaml
import ibllib.io.session_params as ses_params

from iblrig.test.base import TASK_KWARGS
from iblrig.base_tasks import SoundMixin, RotaryEncoderMixin, BaseSession, BpodMixin, ValveMixin
from iblrig.base_choice_world import BiasedChoiceWorldSession


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
        task_settings_file = BiasedChoiceWorldSession.base_parameters_file
        self.session = BaseSession(task_parameter_file=task_settings_file, **TASK_KWARGS)

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

    def test_sound_card_mixin(self):
        """
        Instantiates a bare session with the sound card mixin
        """
        session = self.session
        SoundMixin.init_mixin_sound(session)
        assert session.sound.OUT_TONE is None

    def test_bpod_mixin(self):
        session = self.session
        BpodMixin.init_mixin_bpod(session)
        assert hasattr(session, 'bpod')

    def test_valve_mixin(self):
        session = self.session
        ValveMixin.init_mixin_valve(session)
        # assert session.valve.compute < 1
        assert not session.valve.is_calibrated


class TestExperimentDescription(unittest.TestCase):
    """Test creation of experiment description dictionary."""

    def setUp(self) -> None:
        self.stub = {
            'version': '1.0.0',
            'tasks': [{'choiceWorld': {'collection': 'raw_behavior_data', 'sync': 'bpod'}}],
            'procedures': ['Imaging'],
            'projects': ['foo'],
            'devices': {
                'bpod': {'bpod': {'foo': 10, 'bar': 20}},
                'cameras': {'left': {'baz': 0}}}
        }
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.stub_path = ses_params.write_params(tempdir.name, self.stub)

    def test_new_description(self):
        """Test creation of a brand new experiment description (no stub)"""
        hardware_settings = {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3',
            'device_bpod': {'FOO': 10, 'BAR': 20},
            'device_camera': {'BAZ': 0}
        }
        description = BaseSession.make_experiment_description(
            'choiceWorld', 'raw_behavior_data', procedures=['Imaging'], projects=['foo'], hardware_settings=hardware_settings)
        expected = {k: v for k, v in self.stub.items() if k != 'version'}
        self.assertDictEqual(expected, description)

        # Test with sub keys
        hardware_settings['device_cameras'] = {'left': {'BAZ': 0}}
        description = BaseSession.make_experiment_description(
            'choiceWorld', 'raw_behavior_data', procedures=['Imaging'], projects=['foo'], hardware_settings=hardware_settings)
        self.assertDictEqual(expected, description)

        # Test sync
        hardware_settings['MAIN_SYNC'] = True
        description = BaseSession.make_experiment_description(
            'choiceWorld', 'raw_behavior_data', hardware_settings=hardware_settings)
        expected = {'bpod': {'collection': 'raw_behavior_data', 'sync': 'bpod'}}
        self.assertDictEqual(expected, description.get('sync', {}))

    def test_stub(self):
        """Test merging of experiment description with a stub"""
        hardware_settings = {
            'RIG_NAME': '_iblrig_cortexlab_behavior_3',
            'device_bpod': {'FOO': 20, 'BAR': 30},
            'device_foo': {'one': {'BAR': 'baz'}}
        }
        description = BaseSession.make_experiment_description(
            'passiveWorld', 'raw_task_data_00', projects=['foo', 'bar'], hardware_settings=hardware_settings, stub=self.stub_path)
        self.assertCountEqual(['Imaging'], description['procedures'])
        self.assertCountEqual(['bar', 'foo'], description['projects'])
        self.assertCountEqual(['cameras', 'bpod', 'foo'], description.get('devices', {}).keys())
        bpod_device = description.get('devices', {}).get('bpod', {})
        self.assertDictEqual({'bpod': {'foo': 20, 'bar': 30}}, bpod_device)
        expected = self.stub['tasks'] + [{'passiveWorld': {'collection': 'raw_task_data_00', 'sync_label': 'bpod'}}]
        self.assertCountEqual(expected, description.get('tasks', []))
