"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.

"""
from pathlib import Path
import unittest

import iblrig
from iblrig.base_tasks import SoundMixin, RotaryEncoderMixin, BaseSession, BpodMixin, ValveMixin


class TestHardwareMixins(unittest.TestCase):
    def setUp(self):
        task_settings_file = Path(iblrig.__file__).parents[1].joinpath(
            'iblrig_tasks/_iblrig_tasks_biasedChoiceWorld/task_parameters.yaml')
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
