"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.
"""

import unittest
from unittest import mock

from iblrig.base_choice_world import ChoiceWorldSession
from iblrig.base_tasks import (
    BaseSession,
    BonsaiRecordingMixin,
    BonsaiVisualStimulusMixin,
    BpodMixin,
    Frame2TTLMixin,
    RotaryEncoderMixin,
    SoundMixin,
    ValveMixin,
)
from iblrig.hardware import SOFTCODE
from iblrig_tests.base import TASK_KWARGS


class EmptyHardwareSession(BaseSession):
    protocol_name = 'empty_hardware_session_for_testing'

    def start_hardware(self):
        pass

    def _run(self):
        pass


def mixin_factory(*cls_mixin):
    """
    Composes the empty hardware session class with a single mixin for testing purposes
    :param cls_mixin:
    :return:
    """

    class TestMixin(EmptyHardwareSession, *cls_mixin):
        pass

    session = TestMixin(task_parameter_file=ChoiceWorldSession.base_parameters_file, **TASK_KWARGS)
    return session


class BaseTestHardwareMixins(unittest.TestCase):
    def setUp(self):
        task_settings_file = ChoiceWorldSession.base_parameters_file
        self.session = EmptyHardwareSession(task_parameter_file=task_settings_file, **TASK_KWARGS)


class TestBonsaiMixins(unittest.TestCase):
    @mock.patch('iblrig.base_tasks.call_bonsai')
    def test_bonsai_recording_mixin(self, mock_call_bonsai):
        # create a session with the bonsai recording mixin only and all tests parameters
        session = mixin_factory(BonsaiRecordingMixin)
        session.init_mixin_bonsai_recordings()
        # this will fail if the udp clients are not alive, which they should be
        session.bonsai_camera.udp_client.send2bonsai(trial_num=6, sim_freq=50)
        session.bonsai_microphone.udp_client.send2bonsai(trial_num=6, sim_freq=50)
        # test the camera + microphone recording as in the behavior
        session.start_mixin_bonsai_cameras()
        session.trigger_bonsai_cameras()
        # test the single microphone recording
        session.hardware_settings.device_cameras = None
        session.start_mixin_bonsai_microphone()
        session.stop_mixin_bonsai_recordings()

    @mock.patch('iblrig.base_tasks.call_bonsai')
    def test_bonsai_visual_stimulus_mixin(self, _):
        session = mixin_factory(BonsaiVisualStimulusMixin)
        session.start_mixin_bonsai_visual_stimulus()
        session.init_mixin_bonsai_visual_stimulus()
        session.choice_world_visual_stimulus()
        session.run_passive_visual_stim()
        session.stop_mixin_bonsai_visual_stimulus()


class TestBpodMixin(unittest.TestCase):
    def test_bpod_mixin(self):
        session = mixin_factory(BpodMixin)
        session.init_mixin_bpod()
        assert hasattr(session, 'bpod')
        with self.assertRaises(ValueError):
            session.start_mixin_bpod()

    def test_softcode_dict(self):
        session = mixin_factory(BpodMixin, SoundMixin)
        softcode_dict = session.softcode_dictionary()
        self.assertIsInstance(softcode_dict, dict)
        self.assertIsNone(session.bpod.softcodes)  # will only be assigned a dict value in `start_hardware`
        with self.assertRaises(ValueError):
            softcode_dict[SOFTCODE.TRIGGER_CAMERA]()  # since we didn't instantiate with CameraMixin


class TestOtherMixins(BaseTestHardwareMixins):
    def test_rotary_encoder_mixin(self):
        """
        Instantiates a bare session with the rotary encoder mixin
        """
        session = self.session
        RotaryEncoderMixin.init_mixin_rotary_encoder(session)
        assert session.device_rotary_encoder.ENCODER_EVENTS == [
            'RotaryEncoder1_1',
            'RotaryEncoder1_2',
            'RotaryEncoder1_3',
            'RotaryEncoder1_4',
        ]
        assert {
            -35: 'RotaryEncoder1_1',
            35: 'RotaryEncoder1_2',
            -2: 'RotaryEncoder1_3',
            2: 'RotaryEncoder1_4',
        } == session.device_rotary_encoder.THRESHOLD_EVENTS
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

    def test_valve_mixin(self):
        session = self.session
        ValveMixin.init_mixin_valve(session)
        # assert session.valve.compute < 1
        assert not session.valve.is_calibrated
