# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, September 27th 2018, 6:32:28 pm
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-09-28 15:26:50

import numpy as np
import subprocess
import os
import sys
import platform
import logging

from pybpod_soundcard_module.module import SoundCard, SoundCommandType
from pybpod_soundcard_module.module_api import (SoundCardModule, DataType,
    SampleRate)
log = logging.getLogger('iblrig')


def configure_sounddevice(sd=None, output='sysdefault', samplerate=44100):
    """
    Will import, configure, and return sounddevice module to
    play sounds using onboard sound card.

    :param sd: sounddevice module to be configured,
            defaults to None, will import new module if absent.
    :type sd: module, optional
    :return: configured sounddevice module
    :rtype: sounddevice module
    """
    if not output:
        return
    if sys.platform == 'linux' or platform.node() == 'IBLRIG000':
        output = 'sysdefault'
    if sd is None:
        import sounddevice as sd
    if output == 'xonar':
        devices = sd.query_devices()
        sd.default.device = [(i, d) for i, d in enumerate(
            devices) if 'XONAR SOUND CARD(64)' in d['name']][0][0]
        sd.default.latency = 'low'
        sd.default.channels = 2
        sd.default.samplerate = samplerate
    elif output == 'sysdefault':
        sd.default.latency = 'low'
        sd.default.channels = 2
        sd.default.samplerate = samplerate
    return sd


def make_sound(rate=44100, frequency=5000, duration=0.1, amplitude=1,
               fade=0.01, chans='L+TTL'):
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

    tvec = np.linspace(0, tone_duration, tone_duration * sample_rate)
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
    one_ms = round(sample_rate/1000) * 10
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


def format_sound(sound, file_path=None):
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
    return bin_sound


def upload(wave_int, sound_index):
    """
    Upload a wave_int to an sound_index of the non volatile memory of the
    sound card.

    :param wave_int: path of executable for transferring sounds
    :type wave_int: numpy.ndarray
    :param sound_index: E[2-31] memory bank to upload to
    :type sound_index: int
    """
    card = SoundCardModule()
    if sys.platform == 'linux':
        return
    card.open()
    # send sound
    card.send_sound(wave_int, sound_index, SampleRate._96000HZ, DataType.INT32)

    return


def get_uploaded_sounds():
    pass


def sound_sample_freq(soft_sound):
    if soft_sound == 'xonar':
        ssf = 192000
    elif soft_sound == 'sysdefault':
        ssf = 44100
    elif soft_sound is None:
        ssf = 96000

    return ssf


def init_sounds(sph_obj, tone=True, noise=True):
    if not sph_obj.SOFT_SOUND:
        msg = f"""
    ##########################################
    SOUND BOARD NOT IMPLEMTNED YET!!",
    PLEASE GO TO:
    iblrig_params/IBL/tasks/{sph_obj.PYBPOD_PROTOCOL}/task_settings.py
    and set
        SOFT_SOUND = 'sysdefault' or 'xonar'
    ##########################################"""
        log.error(msg)
        raise(NotImplementedError)
    if tone:
        sph_obj.GO_TONE = make_sound(
            rate=sph_obj.SOUND_SAMPLE_FREQ,
            frequency=sph_obj.GO_TONE_FREQUENCY,
            duration=sph_obj.GO_TONE_DURATION,
            amplitude=sph_obj.GO_TONE_AMPLITUDE,
            fade=0.01,
            chans='L+TTL')
    if noise:
        sph_obj.WHITE_NOISE = make_sound(
            rate=sph_obj.SOUND_SAMPLE_FREQ,
            frequency=-1,
            duration=sph_obj.WHITE_NOISE_DURATION,
            amplitude=sph_obj.WHITE_NOISE_AMPLITUDE,
            fade=0.01,
            chans='L+TTL')
    return sph_obj


if __name__ == '__main__':
    # sd = configure_sounddevice(output='xonar')
    # sd.stop()
    # L_TTL = make_sound(chans='L+TTL', amplitude=0.2)
    # N_TTL = make_sound(chans='L+TTL', amplitude=-1)
    # sd.play(L_TTL, 44100, mapping=[1, 2])
    SOFT_SOUND = None
    SOUND_SAMPLE_FREQ = sound_sample_freq(SOFT_SOUND)
    SOUND_BOARD_BPOD_PORT = 'Serial3'
    WHITE_NOISE_DURATION = float(0.5)
    WHITE_NOISE_AMPLITUDE = float(0.05)
    GO_TONE_DURATION = float(0.1)
    GO_TONE_FREQUENCY = int(5000)
    GO_TONE_AMPLITUDE = float(0.1)
    GO_TONE = make_sound(
        rate=SOUND_SAMPLE_FREQ, frequency=GO_TONE_FREQUENCY,
        duration=GO_TONE_DURATION, amplitude=GO_TONE_AMPLITUDE,
        fade=0.01, chans='stereo')
    WHITE_NOISE = make_sound(
        rate=SOUND_SAMPLE_FREQ, frequency=-1,
        duration=WHITE_NOISE_DURATION,
        amplitude=WHITE_NOISE_AMPLITUDE, fade=0.01, chans='stereo')
    GO_TONE_IDX = 2
    WHITE_NOISE_IDX = 3
    upload(format_sound(GO_TONE), GO_TONE_IDX)
    upload(format_sound(WHITE_NOISE), WHITE_NOISE_IDX)

    print('i')
