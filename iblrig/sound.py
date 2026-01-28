import logging
from os import PathLike
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import NonNegativeFloat, PositiveFloat, PositiveInt, validate_call

from pybpod_soundcard_module.module_api import DataType, SampleRate, SoundCardModule

log = logging.getLogger(__name__)


def sine_wave(d: float, f: float, fs: int = 44100) -> np.ndarray:
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


def apply_hanning_envelope(waveform: np.ndarray, d: float, fs: int = 44100) -> np.ndarray:
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
    if d == 0.0:
        return waveform
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


@validate_call
def sine_stimulus(
    d: PositiveFloat,
    f: PositiveFloat,
    fs: PositiveInt = 44100,
    amplitude: NonNegativeFloat = 1.0,
    gain_db: float = 0.0,
    d_fade: NonNegativeFloat = 0.01,
) -> np.ndarray:
    """
    Generate a sine wave stimulus: A sine wave with a Hanning fade-in and fade-out, defined amplitude and gain.

    Parameters
    ----------
    d : float
        Duration of the sine wave in seconds. Must be positive.
    f : float
        Frequency of the sine wave in Hertz (Hz). Must be positive.
    fs : int, optional
        Sampling rate in samples per second (Hz). Must be positive. Default is 44100.
    amplitude : float, optional
        Base amplitude of the tone before gain adjustment. Must be non-negative. Default is 1.0.
    gain_db: float = 0.0
        Gain adjustment in decibels. Positive to amplify, negative to attenuate. Default is 0.0.
    d_fade : float
        Duration of Hanning fade-in and fade-out sections in seconds. Must be non-negative. Default is 0.01 (10 ms).
    """
    stimulus = sine_wave(d=d, f=f, fs=fs)
    stimulus = apply_hanning_envelope(waveform=stimulus, d=d_fade, fs=fs)
    stimulus *= amplitude
    stimulus *= 10 ** (gain_db / 20)
    return stimulus


@validate_call
def white_noise_stimulus(
    d: PositiveFloat,
    fs: PositiveInt = 44100,
    amplitude: NonNegativeFloat = 1.0,
    gain_db: float = 0.0,
    d_fade: NonNegativeFloat = 0.0,
) -> np.ndarray:
    """
    Generate a sine wave stimulus: zero-mean white noise with a Hanning fade-in and fade-out, defined amplitude and gain.

    Parameters
    ----------
    d : float
        Duration of the waveform in seconds. Must be positive.
    fs : int, optional
        Sampling rate in samples per second (Hz). Must be positive. Default is 44100.
    amplitude : float, optional
        Base amplitude of the waveform before gain adjustment. Must be non-negative. Default is 1.0.
    gain_db: float = 0.0
        Gain adjustment in decibels. Positive to amplify, negative to attenuate. Default is 0.0.
    d_fade : float
        Duration of Hanning fade-in and fade-out sections in seconds. Must be non-negative. Default is 0.0 (no fade).

    Returns
    -------
    np.ndarray
        Array of uniform white noise samples in [-amplitude, amplitude].
    """
    stimulus = np.random.rand(int(fs * d)) * 2 - 1
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
    chans: Literal['mono', 'L', 'R', 'stereo', 'L+TTL', 'TTL+R', 'left', 'right'] = 'L+TTL',
    gain_db: float = 0.0,
) -> np.ndarray:
    """
    Generate a sound waveform with optional fade and channel configurations.

    Parameters
    ----------
    rate : int, optional
        Sampling rate in Hz. Default is 44100.
    frequency : float, optional
        Frequency of the tone in Hz. Negative values will result in white noise. Default is 5000.
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
    gain_db: float = 0.0
        Gain adjustment in decibels. Positive to amplify, negative to attenuate. Default is 0.0.

    Returns
    -------
    np.ndarray
        The generated sound waveform, shape (samples,) for mono or (samples, 2) for stereo.
    """
    if frequency < 0:
        tone = white_noise_stimulus(d=duration, fs=rate, amplitude=amplitude, gain_db=gain_db, d_fade=fade)
    else:
        tone = sine_stimulus(d=duration, f=frequency, fs=rate, amplitude=amplitude, gain_db=gain_db, d_fade=fade)

    ttl = np.ones(len(tone)) * 0.99
    ttl[round(rate / 100) :] = 0  # 10 ms TTL
    null = np.zeros(len(tone))

    match chans:
        case 'mono':
            sound = tone
        case chans if chans in ['L', 'left']:
            sound = np.column_stack((tone, null))
        case chans if chans in ['R', 'right']:
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


def format_sound(sound: np.ndarray, file_path: PathLike | str | None = None, flat: bool = False) -> np.ndarray:
    """
    Format a stereo sound array into a binary-compatible int32 format.

    This formats the audio data for output to a sound card. The sound is expected
    to be stereo (2 channels) and in float format [-1.0, 1.0]. The result is an
    array of int32 values interleaved [L, R, L, R, ...].

    Parameters
    ----------
    sound : np.ndarray
        A 2D NumPy array of shape (n_samples, 2) containing stereo float audio data.
    file_path : PathLike or str, optional
        If provided, the formatted audio will be written to this binary file.
    flat : bool, optional
        If True, return a 1D flattened array. Otherwise, return (n_samples, 2) shape.

    Returns
    -------
    np.ndarray
        The formatted int32 sound array, either flattened or in original shape.

    Raises
    ------
    ValueError
        If `sound` is not a 2D array with shape (n_samples, 2).
    """
    if sound.ndim != 2 or sound.shape[1] != 2:
        raise ValueError('Sound must be a 2D array with shape (n_samples, 2) for stereo output.')

    bin_sound = (sound * ((2**31) - 1)).astype(np.int32)  # Scale from float [-1.0, 1.0] to int32 range
    bin_sound = np.ascontiguousarray(bin_sound)  # Ensure memory layout is contiguous
    interleaved = bin_sound.reshape(-1)  # Interleave the samples as a 1D array: [L, R, L, R, ...]

    # Optionally save to binary file
    if file_path is not None:
        Path(file_path).write_bytes(interleaved.tobytes())

    return bin_sound.flatten() if flat else bin_sound


def configure_sound_card(
    card: SoundCardModule | None = None,
    sounds: list[np.ndarray] | None = None,
    indexes: list[int] | None = None,
    sample_rate: int = 96000,
) -> None:
    """
    Configure a Harp sound card with given sounds at specified indexes and sample rate.

    Parameters
    ----------
    card : SoundCardModule, optional
        An instance of the sound card interface to send sounds to.
        If None, a new SoundCardModule instance will be created and closed after use.
        Default is None.
    sounds : list of np.ndarray, optional
        A list of stereo sound arrays to be formatted and sent to the card.
        Each sound array should be 2D (n_samples, 2). Default is None (empty list).
    indexes : list of int, optional
        List of indexes corresponding to each sound in `sounds`.
        Must be the same length as `sounds`. All values must be in range [2, 32].
        Default is None (empty list).
    sample_rate : int, optional
        Sample rate in Hz for playback. Must be 96000 or 192000. Default is 96000.

    Raises
    ------
    ValueError
        If `sample_rate` is not 96000 or 192000.
        If the lengths of `sounds` and `indexes` do not match.
        If one or several indices are outside valid range.
    """
    if indexes is None:
        indexes = []
    if sounds is None:
        sounds = []
    close_card = card is None
    if card is None:
        card = SoundCardModule()

    if len(sounds) != len(indexes):
        raise ValueError('Number of sounds and indices must match')
    if not all([2 <= idx <= 32 for idx in indexes]):
        raise ValueError('One or more indices out of valid range [2, 32]')

    # yes, this is painful - send_sound() complains if sample_rate is not type SampleRate
    if sample_rate == 192000:
        sample_rate = SampleRate._192000HZ
    elif sample_rate == 96000:
        sample_rate = SampleRate._96000HZ
    else:
        raise ValueError(f'Sound sample rate {sample_rate} must be 96000 or 192000')

    sounds = [format_sound(s, flat=True) for s in sounds]
    for sound, index in zip(sounds, indexes, strict=False):
        card.send_sound(sound, index, sample_rate, DataType.INT32)

    if close_card:
        card.close()
