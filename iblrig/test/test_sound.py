from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from iblrig import sound
from pybpod_soundcard_module.module_api import DataType


class TestSineWave:
    def test_basic_properties(self):
        duration = 1.0  # seconds
        frequency = 440  # Hz
        fs = 44100

        wave = sound.sine_wave(d=duration, f=frequency, fs=fs)

        assert isinstance(wave, np.ndarray)
        assert wave.ndim == 1
        assert len(wave) == int(fs * duration)
        assert np.all(np.abs(wave) <= 1.0)

    def test_frequency_content(self):
        f = 440.0
        fs = 44100
        wave = sound.sine_wave(d=1.0, f=f, fs=fs)
        spectrum = np.fft.rfft(wave)
        freqs = np.fft.rfftfreq(len(wave), d=1 / fs)
        peak_freq = freqs[np.argmax(np.abs(spectrum))]
        assert np.isclose(peak_freq, f, atol=1.0), f'Peak freq {peak_freq} != {f}'


class TestApplyHanningEnvelope:
    def test_applies_fade_correctly(self):
        fs = 1000
        fade_duration = 0.1  # 100 ms fade-in and fade-out

        waveform = np.ones(fs)
        enveloped = sound.apply_hanning_envelope(waveform, d=fade_duration, fs=fs)
        assert enveloped.shape == waveform.shape

        n_fade = int(fade_duration * fs)
        assert np.isclose(enveloped[0], 0.0, atol=1e-6)
        assert np.isclose(enveloped[n_fade - 1], 1.0, atol=0.1)
        assert np.isclose(enveloped[-1], 0.0, atol=1e-6)
        assert np.allclose(enveloped[n_fade:-n_fade], 1.0, atol=1e-6)

    def test_raises_on_too_long_fade(self):
        fs = 1000
        waveform = np.ones(100)
        fade_duration = 0.1  # 100 ms => 100 samples; 2 * 100 > 100 ⇒ should fail
        with pytest.raises(ValueError, match='Fade duration is too long'):
            sound.apply_hanning_envelope(waveform, d=fade_duration, fs=fs)

    def test_output_range(self):
        fs = 44100
        waveform = np.random.uniform(low=-1, high=1, size=fs)
        enveloped = sound.apply_hanning_envelope(waveform, d=0.01, fs=fs)
        assert np.max(enveloped) <= np.max(waveform)
        assert np.min(enveloped) >= np.min(waveform)

    def test_zero_fade(self):
        waveform = np.ones(1000)
        enveloped = sound.apply_hanning_envelope(waveform, d=0, fs=44100)
        assert np.array_equal(waveform, enveloped)

    def test_too_short_waveform(self):
        waveform = np.ones(10)
        with pytest.raises(ValueError):
            sound.apply_hanning_envelope(waveform, d=0.01, fs=44100)


class TestSineStimulus:
    def test_basic_output(self):
        d = 1.0
        f = 440
        fs = 44100

        stim = sound.sine_stimulus(d=d, f=f, fs=fs)
        assert isinstance(stim, np.ndarray)
        assert stim.ndim == 1
        assert len(stim) == int(d * fs)
        assert np.max(np.abs(stim)) <= 1.0

    def test_amplitude_and_gain(self):
        d = 0.1
        f = 1000
        fs = 44100

        base = sound.sine_stimulus(d=d, f=f, fs=fs, amplitude=1.0, gain_db=0.0)
        attenuated = sound.sine_stimulus(d=d, f=f, fs=fs, amplitude=1.0, gain_db=-6.0)
        amplified = sound.sine_stimulus(d=d, f=f, fs=fs, amplitude=1.0, gain_db=6.0)
        assert np.max(np.abs(attenuated)) < np.max(np.abs(base))
        assert np.max(np.abs(amplified)) > np.max(np.abs(base))

        stim_amp_2 = sound.sine_stimulus(d=d, f=f, fs=fs, amplitude=2.0, gain_db=0.0)
        assert np.isclose(np.max(np.abs(stim_amp_2)), 2 * np.max(np.abs(base)), rtol=1e-2)

    def test_fade_envelope_applied(self):
        f = 440
        fs = 44100
        d_fade = 0.05
        stim = sound.sine_stimulus(d=1, f=f, fs=fs, d_fade=d_fade)
        n_fade = int(d_fade * fs)
        assert np.isclose(stim[0], 0.0, atol=1e-4)
        assert np.isclose(stim[-1], 0.0, atol=1e-4)
        assert np.max(np.abs(stim[n_fade:-n_fade])) > 0.7

    def test_frequency_content(self):
        f = 1000
        fs = 44100
        stim = sound.sine_stimulus(d=1, f=f, fs=fs)
        spectrum = np.fft.rfft(stim)
        freqs = np.fft.rfftfreq(len(stim), 1 / fs)
        peak_freq = freqs[np.argmax(np.abs(spectrum))]
        assert np.isclose(peak_freq, f, atol=1.0), f'Peak frequency {peak_freq} not close to {f}'


class TestFormatSound:
    def test_output_dtype_and_shape(self):
        stereo_wave = np.array([[0.5, -0.5], [1.0, -1.0], [-0.25, 0.25]], dtype=np.float32)
        result = sound.format_sound(stereo_wave)
        scale = (2**31) - 1
        expected = (stereo_wave * scale).astype(np.int32)
        assert result.shape == (3, 2)
        assert result.dtype == np.int32
        np.testing.assert_array_equal(result, expected)

    def test_flat_output(self):
        stereo_wave = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        flat = sound.format_sound(stereo_wave, flat=True)
        assert flat.ndim == 1
        assert flat.shape == (4,)
        assert flat[::2].tolist() == [flat[0], flat[2]]  # L samples
        assert flat[1::2].tolist() == [flat[1], flat[3]]  # R samples

    def test_file_output(self, tmp_path):
        stereo_wave = np.ones((10, 2), dtype=np.float32) * 0.5
        file_path = tmp_path / 'test_sound.bin'
        _ = sound.format_sound(stereo_wave, file_path=str(file_path))
        assert file_path.exists()
        with open(file_path, 'rb') as f:
            data = f.read()
            assert len(data) == 10 * 2 * 4  # 10 samples x 2 channels x 4 bytes

    def test_invalid_input_raises(self):
        mono_wave = np.ones((10,), dtype=np.float32)  # Not stereo
        with pytest.raises(ValueError, match='Sound must be a 2D array'):
            sound.format_sound(mono_wave)


class DummyCard:
    def __init__(self):
        self.send_sound = MagicMock()
        self.close = MagicMock()


class TestConfigureSoundCard:
    @pytest.fixture
    def dummy_card(self):
        return DummyCard()

    @patch('iblrig.sound.format_sound', side_effect=lambda s, flat=True: s)
    @patch('iblrig.sound.SoundCardModule', autospec=True)
    def test_configure_sound_card(self, mock_card_class, mock_format_sound, dummy_card):
        mock_card_class.return_value = dummy_card

        # Test default card creation and close called
        sounds = [[0.1, 0.2], [0.3, 0.4]]
        indexes = [2, 3]
        sound.configure_sound_card(sounds=sounds, indexes=indexes, sample_rate=96000)
        assert mock_format_sound.call_count == 2

        # send_sound called with formatted sounds, correct indexes and sample rate
        calls = dummy_card.send_sound.call_args_list
        assert len(calls) == 2
        for call, idx in zip(calls, indexes, strict=False):
            args, kwargs = call
            assert args[1] == idx
            assert args[2] == 96000
            assert args[3].name == 'INT32' or args[3] == DataType.INT32

        # card.close called because card was created inside
        dummy_card.close.assert_called_once()

        # Test passing in an existing card disables close
        dummy_card.send_sound.reset_mock()
        dummy_card.close.reset_mock()
        sound.configure_sound_card(card=dummy_card, sounds=sounds, indexes=indexes, sample_rate=192000)
        dummy_card.send_sound.assert_called()
        dummy_card.close.assert_not_called()

        with pytest.raises(ValueError):
            sound.configure_sound_card(card=dummy_card, sounds=sounds, indexes=indexes, sample_rate=12345)
        with pytest.raises(ValueError):
            sound.configure_sound_card(card=dummy_card, sounds=sounds, indexes=[4])
        with pytest.raises(ValueError):
            sound.configure_sound_card(card=dummy_card, sounds=sounds, indexes=[0, 1])
        with pytest.raises(ValueError):
            sound.configure_sound_card(card=dummy_card, sounds=sounds, indexes=[32, 33])
