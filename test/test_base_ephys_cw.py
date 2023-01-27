"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.

"""
from pathlib import Path
import unittest
import tempfile
import yaml

from iblrig.base_tasks import SoundMixin, RotaryEncoderMixin, BaseSession, BpodMixin, ValveMixin
from iblrig.base_choice_world import BiasedChoiceWorldSession


class TestHierarchicalParameters(unittest.TestCase):

    def test_default_params(self):
        sess = BiasedChoiceWorldSession()
        with tempfile.NamedTemporaryFile() as tf:
            with open(tf.name, 'w+') as fp:
                yaml.safe_dump(data={'TITI': 1, 'REWARD_AMOUNT_UL': -2}, stream=fp)
            sess2 = BiasedChoiceWorldSession(task_parameter_file=Path(tf.name))
        assert len(sess2.task_params.keys()) == len(sess.task_params.keys()) + 1
        assert sess2.task_params['TITI'] == 1
        assert sess2.task_params['REWARD_AMOUNT_UL'] == -2


class TestHardwareMixins(unittest.TestCase):
    def setUp(self):
        task_settings_file = BiasedChoiceWorldSession.base_parameters_file
        self.session = BaseSession(task_parameter_file=task_settings_file,
                                   hardware_settings_name='hardware_settings_template.yaml')

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
