"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.

"""
from pathlib import Path
import unittest

import iblrig
from iblrig.base_tasks import SoundMixin, RotaryEncoderMixin, BaseSessionParamHandler, BpodMixin, ValveMixin


class TestHardwareMixins(unittest.TestCase):
    def setUp(self):
        task_settings_file = Path(iblrig.__file__).parents[1].joinpath(
            'pybpod_fixtures/IBL/tasks/_iblrig_tasks_biasedChoiceWorld/task_parameters.yaml')
        self.session = BaseSessionParamHandler(task_settings_file=task_settings_file,
                                               hardware_settings_name='hardware_settings_template.yaml')

    def test_rotary_encoder_mixin(self):
        """
        Instantiates a bare session with the rotary encoder mixin
        """
        session = self.session
        RotaryEncoderMixin.__init__(session)
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
        SoundMixin.__init__(session)
        session.sound.OUT_TONE == ('SoftCode', 1)
        session.sound.OUT_NOISE == ('SoftCode', 2)
        session.sound.OUT_STOP_SOUND == ('SoftCode', 0)

    def test_bpod_mixin(self):
        session = self.session
        BpodMixin.__init__(session)
        assert hasattr(session, 'bpod')

    def test_valve_mixin(self):
        session = self.session
        ValveMixin.__init__(session)
        assert session.valve.reward_time < 1
        assert not session.valve.is_calibrated
