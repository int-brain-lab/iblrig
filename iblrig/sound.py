import logging
from typing import Literal

import numpy as np

from pybpod_soundcard_module.module_api import DataType, SampleRate, SoundCardModule

log = logging.getLogger(__name__)


def sine_wave(d: float, f: float, fs: int = 44100):
    """
    Generate a sine wave signal.

    Parameters
    ----------
    d : float
        Duration of the sine wave in seconds. Must be positive.
    f : float
        Frequency of the sine wave in Hertz (Hz). Must be positive.
    fs : int, optional
        Sampling rate in samples per second (Hz). Default is 44100.

    Returns
    -------
    np.ndarray
        Array containing the sine wave samples.
    """
    t = np.arange(d * fs) / fs
    return np.sin(2 * np.pi * f * t)


def apply_hanning_envelope(waveform: np.ndarray, d: float, fs: int = 44100):
    """
    Apply a Hanning fade-in and fade-out to an audio waveform.

    Parameters
    ----------
    waveform : np.ndarray
        The input audio waveform (1D array of samples).
    d : float
        Duration of the fade-in and fade-out sections in seconds.
    fs : int, optional
        Sampling rate in samples per second (Hz). Default is 44100.

    Returns
    -------
    np.ndarray
        The waveform with the Hanning amplitude envelope applied.

    Raises
    ------
    ValueError
        If the fade duration is too long.
    """
    n_samples_waveform = len(waveform)
    n_samples_fade = int(d * fs)
    if 2 * n_samples_fade > n_samples_waveform:
        raise ValueError('Fade duration is too long for the waveform length.')

    # generate Hanning window and split into fade-in and fade-out
    window = np.hanning(2 * n_samples_fade)
    fade_in = window[:n_samples_fade]
    fade_out = window[n_samples_fade:]

    # apply envelope to waveform
    sustain = np.ones(n_samples_waveform - 2 * n_samples_fade)
    envelope = np.concatenate([fade_in, sustain, fade_out])
    return waveform * envelope


def sine_stimulus(
    d: float | int, f: float | int, fs: int = 44100, amplitude: float = 1.0, gain_db: float = 0.0, d_fade: float = 0.01
):
    """
    Generate a sine wave stimulus.

    Parameters
    ----------
    d : float or int
        Duration of the sine wave in seconds. Must be positive.
    f : float or int
        Frequency of the sine wave in Hertz (Hz). Must be positive.
    fs : int, optional
        Sampling rate in samples per second (Hz). Default is 44100.
    amplitude : float, optional
        Base amplitude of the tone before gain adjustment. Default is 1.0.
    gain_db: float = 0.0
        Gain adjustment in decibels. Positive to amplify, negative to attenuate. Default is 0.0.
    d_fade : float or int
        Duration of the fade-in and fade-out sections in seconds.
    """
    stimulus = sine_wave(d=d, f=f, fs=fs)
    stimulus = apply_hanning_envelope(waveform=stimulus, d=d_fade, fs=fs)
    stimulus *= amplitude
    stimulus *= 10 ** (gain_db / 20)
    return stimulus


def make_sound(
    rate: int = 44100,
    frequency: float = 5000,
    duration: float = 0.1,
    amplitude: float = 1,
    fade: float = 0.01,
    chans: Literal['mono', 'L', 'R', 'stereo', 'L+TTL', 'TTL+R'] = 'L+TTL',
):
    """
    Generate a sound waveform with optional fade and channel configurations.

    Parameters
    ----------
    rate : int, optional
        Sampling rate in Hz. Default is 44100.
    frequency : float, optional
        Frequency of the tone in Hz. If -1, generates white noise. Default is 5000.
    duration : float, optional
        Duration of the sound in seconds. Default is 0.1.
    amplitude : float, optional
        Amplitude of the tone. Default is 1.
    fade : float, optional
        Duration of fade-in and fade-out in seconds. Default is 0.01.
    chans : str, optional
        Output channel configuration:
        - 'mono': single channel
        - 'L': tone on left channel only
        - 'R': tone on right channel only
        - 'stereo': tone on both channels
        - 'L+TTL': tone on left, TTL pulse on right
        - 'TTL+R': TTL pulse on left, tone on right
        Default is 'L+TTL'.

    Returns
    -------
    np.ndarray
        The generated sound waveform, shape (samples,) for mono or (samples, 2) for stereo.
    """
    if frequency == -1:
        tone = amplitude * np.random.rand(int(rate * duration))
    else:
        tone = sine_stimulus(d=duration, f=frequency, fs=rate, amplitude=amplitude, d_fade=fade)

    ttl = np.ones(len(tone)) * 0.99
    ttl[round(rate / 100):] = 0  # 10 ms TTL
    null = np.zeros(len(tone))

    match chans:
        case 'mono':
            sound = tone
        case 'L':
            sound = np.column_stack((tone, null))
        case 'R':
            sound = np.column_stack((null, tone))
        case 'stereo':
            sound = np.column_stack((tone, tone))
        case 'L+TTL':
            sound = np.column_stack((tone, ttl))
        case 'TTL+R':
            sound = np.column_stack((ttl, tone))
        case _:
            raise ValueError(f'Unsupported channel configuration: {chans}')
    return sound


def format_sound(sound, file_path=None, flat=False):
    """
    Format sound to send to sound card.

    Binary files to be sent to the sound card need to be a single contiguous
    vector of int32 s. 4 Bytes left speaker, 4 Bytes right speaker, ..., etc.


    :param sound: Stereo sound
    :type sound: 2d numpy.array os shape (n_samples, 2)
    :param file_path: full path of file. [default: None]
    :type file_path: str
    """
    bin_sound = (sound * ((2**31) - 1)).astype(np.int32)

    if bin_sound.flags.f_contiguous:
        bin_sound = np.ascontiguousarray(bin_sound)

    bin_save = bin_sound.reshape(1, np.multiply(*bin_sound.shape))
    bin_save = np.ascontiguousarray(bin_save)

    if file_path:
        with open(file_path, 'wb') as bf:
            bf.writelines(bin_save)
            bf.flush()

    return bin_sound.flatten() if flat else bin_sound


def configure_sound_card(card=None, sounds=None, indexes=None, sample_rate=96):
    if indexes is None:
        indexes = []
    if sounds is None:
        sounds = []
    if card is None:
        card = SoundCardModule()
        close_card = True

    if sample_rate in (192, 192000):
        sample_rate = SampleRate._192000HZ
    elif sample_rate in (96, 96000):
        sample_rate = SampleRate._96000HZ
    else:
        log.error(f'Sound sample rate {sample_rate} should be 96 or 192 (KHz)')
        raise (ValueError)

    if len(sounds) != len(indexes):
        log.error('Wrong number of sounds and indexes')
        raise (ValueError)

    sounds = [format_sound(s, flat=True) for s in sounds]
    for sound, index in zip(sounds, indexes, strict=False):
        card.send_sound(sound, index, sample_rate, DataType.INT32)

    if close_card:
        card.close()
