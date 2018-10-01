# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, September 27th 2018, 6:32:28 pm
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-09-28 15:26:50

import numpy as np
import subprocess
import os
import sys


def configure_sounddevice(sd=None):
    """
    Will import, configure, and return sounddevice module to
    play sounds using onboard sound card.

    :param sd: sounddevice module to be configured,
            defaults to None, will import new module if absent.
    :type sd: module, optional
    :return: configured sounddevice module
    :rtype: sounddevice module
    """
    if sd is None:
        import sounddevice as sd
    if sys.platform == 'linux':
        sd.default.device = 'default'
    else:
        devices = sd.query_devices()
        sd.default.device = [(i, d) for i, d in enumerate(
            devices) if 'Speakers' in d['name']][0][0]
    sd.default.latency = 'low'
    sd.default.channels = 8
    return sd


def make_sound(rate=44100, frequency=10000, duration=0.1, amplitude=1,
            fade=0.01, save_path=False):
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
    :param save_path: path of where to save the bin file for upload to card.
                    Will not save if False, defaults to False
    :type save_path: bool/str, optional
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

    if frequency == -1:
        tone = amplitude * np.random.rand(tone.size)

    sound = np.array([tone, tone]).T
    if save_path:
        self.save_bin(sound, save_path)

    return sound


def save_bin(sound, file_path):
    """
    Save binary file for CFSoundcard upload.

    Binary files to be sent to the sound card need to be a single contiguous
    vector of int32 s. 4 Bytes left speaker, 4 Bytes right speaker, ..., etc.


    :param sound: Stereo sound
    :type sound: 2d numpy.array os shape (n_samples, 2)
    :param file_path: full path (w/ name) of location where to save the file
    :type file_path: str
    """
    bin_sound = (sound * ((2**31) - 1)).astype(np.int32)

    if bin_sound.flags.f_contiguous:
        bin_sound = np.ascontiguousarray(bin_sound)

    bin_save = bin_sound.reshape(1, np.multiply(*bin_sound.shape))
    bin_save = np.ascontiguousarray(bin_save)

    with open(file_path, 'wb') as bf:
        bf.writelines(bin_save)


def uplopad(uploader_tool, file_path, index, type_=0, sample_rate=96):
    """
    Uploads a bin file to an index of the non volatile memory of the sound card.

    :param uploader_tool: path of executable for transferring sounds
    :type uploader_tool: str
    :param file_path: path of file to be uploaded
    :type file_path: str
    :param index: E[2-31] memory bank to upload to
    :type index: int
    :param type_: {0: int32, 1: float32} datatype of binary file, defaults to 0
    :param type_: int, optional
    :param sample_rate: [96, 192] (KHz) playback sample rate, defaults to 96
    :param sample_rate: int, optional
    """
    file_name = file_path.split(os.sep)[-1]
    file_folder = file_path.split(os.sep)[:-1]
    subprocess.call([uploader_tool, file_path, index, type_, sample_rate])

    log_file = os.path.join(file_folder, 'log')
    with open(log_file, 'a') as f:
    return


def get_uploaded_sounds():
    pass


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    # sample_rate = 96000
    # duration=0.1
    # amplitude=1
    # fade=0.01
    # frequency=10000

    # sample_rate = 96000  # sample rate, depend on the sound card
    # tone_duration = duration  # sec
    # fade_duration = fade  # sec

    # tvec = np.linspace(0, tone_duration, tone_duration * sample_rate)
    # tone = amplitude * np.sin(2 * np.pi * frequency * tvec)  # tone vec

    # len_fade = int(fade_duration * sample_rate)
    # fade_io = np.hanning(len_fade * 2)
    # fadein = fade_io[:len_fade]
    # fadeout = fade_io[len_fade:]
    # win = np.ones(len(tvec))
    # win[:len_fade] = fadein
    # win[-len_fade:] = fadeout
    # tone = tone * win

    # sound = np.array([tone, tone]).T
    # bin_sound = (sound * ((2**31) - 1)).astype(np.int32)
    # if bin_sound.flags.f_contiguous:
    #     bin_sound = np.ascontiguousarray(bin_sound)

    # bin_save = bin_sound.reshape(1, np.multiply(*bin_sound.shape))

    # bin_save = np.ascontiguousarray(bin_save)

    # file_path = 'some_file'

    # with open(file_path, 'wb') as bf:
    #     bf.writelines(bin_save)


    # plt.plot(tone)
    # plt.show()

    # print('')
