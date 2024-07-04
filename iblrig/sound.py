import logging

import numpy as np
from scipy.signal import chirp

from pybpod_soundcard_module.module_api import DataType, SampleRate, SoundCardModule

log = logging.getLogger(__name__)


def make_sound(rate=44100, frequency=5000, duration=0.1, amplitude=1, fade=0.01, chans='L+TTL'):
    """
    Build sounds and save bin file for upload to soundcard or play via
    sounddevice lib.

    :param rate: sample rate of the soundcard use 96000 for Bpod,
                    defaults to 44100 for soundcard
    :type rate: int, optional
    :param frequency: (Hz) of the tone, if -1 will create uniform random white
                    noise, defaults to 10000
    :type frequency: int, optional
    :param duration: (s) of sound, defaults to 0.1
    :type duration: float, optional
    :param amplitude: E[0, 1] of the sound 1=max 0=min, defaults to 1
    :type amplitude: intor float, optional
    :param fade: (s) time of fading window rise and decay, defaults to 0.01
    :type fade: float, optional
    :param chans: ['mono', 'L', 'R', 'stereo', 'L+TTL', 'TTL+R'] number of
                   sound channels and type of output, defaults to 'L+TTL'
    :type chans: str, optional
    :return: streo sound from mono definitions
    :rtype: np.ndarray with shape (Nsamples, 2)
    """
    sample_rate = rate  # Sound card dependent,
    tone_duration = duration  # sec
    fade_duration = fade  # sec
    chans = chans if isinstance(chans, str) else chans[0]
    tvec = np.linspace(0, tone_duration, int(tone_duration * sample_rate))
    tone = amplitude * np.sin(2 * np.pi * frequency * tvec)  # tone vec

    len_fade = int(fade_duration * sample_rate)
    fade_io = np.hanning(len_fade * 2)
    fadein = fade_io[:len_fade]
    fadeout = fade_io[len_fade:]
    win = np.ones(len(tvec))
    win[:len_fade] = fadein
    win[-len_fade:] = fadeout

    tone = tone * win
    ttl = np.ones(len(tone)) * 0.99
    one_ms = round(sample_rate / 1000) * 10
    ttl[one_ms:] = 0
    null = np.zeros(len(tone))

    if frequency == -1:
        tone = amplitude * np.random.rand(tone.size)

    if chans == 'mono':
        sound = np.array(tone)
    elif chans == 'L':
        sound = np.array([tone, null]).T
    elif chans == 'R':
        sound = np.array([null, tone]).T
    elif chans == 'stereo':
        sound = np.array([tone, tone]).T
    elif chans == 'L+TTL':
        sound = np.array([tone, ttl]).T
    elif chans == 'TTL+R':
        sound = np.array([ttl, tone]).T

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
