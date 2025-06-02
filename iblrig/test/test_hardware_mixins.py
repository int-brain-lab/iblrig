"""
Hardware Mixins are extensions to a Session object for specific hardware.
Those can be instantiated lazily, ie. on any computer.
The start() methods of those mixins require the hardware to be connected.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy.fft import fft, fftfreq
from scipy.stats import ks_2samp

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
from iblrig.test.base import TASK_KWARGS
from iblutil.util import Bunch


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

    @patch('iblrig.test.test_hardware_mixins.EmptyHardwareSession._run')
    @patch('iblrig.test.test_hardware_mixins.EmptyHardwareSession.start_hardware')
    def test_execute_mixins_shared_function(self, mock_start_hardware, mock_run):
        self.session._execute_mixins_shared_function('start_')
        mock_start_hardware.assert_called_once()
        mock_run.assert_not_called()


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

    @patch('iblrig.hardware.Bpod', autospec=True)
    def test_ambient_conversion(self, _):
        session = mixin_factory(BpodMixin)
        assert 'AMBIENT_FILE_PATH' in session.paths
        with TemporaryDirectory() as temp_dir:
            session.paths['AMBIENT_FILE_PATH'] = Path(temp_dir).joinpath(session.paths['AMBIENT_FILE_PATH'].name)
            bin_path = session.paths['AMBIENT_FILE_PATH']
            pqt_path = session.paths['AMBIENT_FILE_PATH'].with_suffix('.pqt')

            bin_path.touch()
            assert bin_path.exists()
            session.stop_mixin_bpod()
            assert not bin_path.exists()
            assert pqt_path.exists()

            data = pd.read_parquet(pqt_path)
            assert 'Trial' in data.columns
            assert 'Temperature_C' in data.columns
            assert 'AirPressure_mb' in data.columns
            assert 'RelativeHumidity' in data.columns


class TestOtherMixins(BaseTestHardwareMixins):
    def test_rotary_encoder_mixin(self):
        """
        Instantiates a bare session with the rotary encoder mixin
        """
        RotaryEncoderSession = type('RotaryEncoderSession', (EmptyHardwareSession, RotaryEncoderMixin), {})  # noqa: N806
        session = RotaryEncoderSession(task_parameter_file=ChoiceWorldSession.base_parameters_file, **TASK_KWARGS)
        assert session.device_rotary_encoder.ENCODER_EVENTS == [
            'RotaryEncoder1_1',
            'RotaryEncoder1_2',
            'RotaryEncoder1_3',
            'RotaryEncoder1_4',
        ]
        assert session.device_rotary_encoder.THRESHOLD_EVENTS == {
            -35: 'RotaryEncoder1_1',
            35: 'RotaryEncoder1_2',
            -2: 'RotaryEncoder1_3',
            2: 'RotaryEncoder1_4',
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
        Test the functionality of the SoundMixin in a session.

        This test checks that the sound card mixin correctly initializes sound
        components and verifies the properties of the generated sounds.
        """
        session = self.session
        SoundMixin.init_mixin_sound(session)

        go_tone = session.sound.get('GO_TONE')
        white_noise = session.sound.get('WHITE_NOISE')
        assert not np.array_equal(go_tone, white_noise)
        fs = session.sound['samplerate']

        # test go tone
        x = go_tone[:, 0]
        n = len(x)
        assert np.isclose(n / fs, 0.11)
        yf = np.abs(fft(x))  # magnitude of the FFT
        xf = fftfreq(n, 1 / fs)  # frequency bins
        idx_peak = np.argmax(yf[: n // 2])  # index of peak magnitude
        assert np.isclose(xf[idx_peak], 5000)
        assert yf[idx_peak] > 100000 * np.median(yf)

        # test white noise
        x = white_noise[:, 0]
        assert np.isclose(len(x) / fs, 0.5)
        _, p_value = ks_2samp(x, np.random.uniform(min(x), max(x), len(x)))
        assert p_value > 0.05

    @patch('iblrig.hardware.Bpod', autospec=True)
    @patch('iblrig.base_tasks.StateMachine', autospec=True)
    def test_sound_card_and_bpod_mixin(self, mock_state_machine, mock_bpod):
        """
        Test the integration of SoundMixin with BpodMixin in a session.

        This test verifies that sound actions are correctly set up and
        executed within the Bpod state machine.
        """
        session = mixin_factory(SoundMixin, BpodMixin)
        session.bpod = mock_bpod.return_value

        session.bpod.actions = Bunch()
        session.bpod.actions['play_tone'] = ('MockSoftCode', 23)
        session.bpod.actions['play_noise'] = ('MockSoftCode', 42)

        # Check the sound play methods
        session.sound_play_tone()
        mock_sma = mock_state_machine.return_value
        kwargs = mock_sma.add_state.call_args.kwargs
        assert kwargs['output_actions'] == [('MockSoftCode', 23)]

        # Check the sound play noise method
        session.sound_play_noise()
        mock_sma = mock_state_machine.return_value
        kwargs = mock_sma.add_state.call_args.kwargs
        assert kwargs['output_actions'] == [('MockSoftCode', 42)]

    def test_valve_mixin(self):
        session = self.session
        ValveMixin.init_mixin_valve(session)
        # assert session.valve.compute < 1
        assert not session.valve.is_calibrated
