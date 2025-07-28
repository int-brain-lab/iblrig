import numpy as np
import pytest

from iblrig import sound


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
