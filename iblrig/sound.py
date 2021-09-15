#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, September 27th 2018, 6:32:28 pm
import logging
import sys

import numpy as np
from pybpod_soundcard_module.module_api import DataType, SampleRate, SoundCardModule
from scipy.signal import chirp

log = logging.getLogger("iblrig")


def configure_sounddevice(sd=None, output="sysdefault", samplerate=44100):
    """
    Will import, configure, and return sounddevice module to
    play sounds using onboard sound card.

    :param sd: sounddevice module to be configured,
            defaults to None, will import new module if absent.
    :type sd: module, optional
    :return: configured sounddevice module
    :rtype: sounddevice module
    """
    if output is None:
        return
    if sys.platform == "linux":  # or platform.node() == 'IBLRIG000':
        output = "sysdefault"
    if sd is None:
        import sounddevice as sd
    if output == "xonar":
        devices = sd.query_devices()
        sd.default.device = [
            (i, d) for i, d in enumerate(devices) if "XONAR SOUND CARD(64)" in d["name"]
        ][0][0]
        sd.default.latency = "low"
        sd.default.channels = 2
        sd.default.samplerate = samplerate
    elif output == "sysdefault":
        sd.default.latency = "low"
        sd.default.channels = 2
        sd.default.samplerate = samplerate
    return sd


def make_sound(rate=44100, frequency=5000, duration=0.1, amplitude=1, fade=0.01, chans="L+TTL"):
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

    if chans == "mono":
        sound = np.array(tone)
    elif chans == "L":
        sound = np.array([tone, null]).T
    elif chans == "R":
        sound = np.array([null, tone]).T
    elif chans == "stereo":
        sound = np.array([tone, tone]).T
    elif chans == "L+TTL":
        sound = np.array([tone, ttl]).T
    elif chans == "TTL+R":
        sound = np.array([ttl, tone]).T

    return sound


def make_chirp(f0=80, f1=160, length=0.1, amp=0.1, fade=0.01, sf=96000):
    t0 = 0
    t1 = length
    t = np.linspace(t0, t1, sf)

    c = amp * chirp(t, f0=f0, f1=f1, t1=t1, method="linear")

    len_fade = int(fade * sf)
    fade_io = np.hanning(len_fade * 2)
    fadein = fade_io[:len_fade]
    fadeout = fade_io[len_fade:]
    win = np.ones(len(t))
    win[:len_fade] = fadein
    win[-len_fade:] = fadeout

    c = c * win
    out = np.array([c, c]).T
    return out


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
    bin_sound = (sound * ((2 ** 31) - 1)).astype(np.int32)

    if bin_sound.flags.f_contiguous:
        bin_sound = np.ascontiguousarray(bin_sound)

    bin_save = bin_sound.reshape(1, np.multiply(*bin_sound.shape))
    bin_save = np.ascontiguousarray(bin_save)

    if file_path:
        with open(file_path, "wb") as bf:
            bf.writelines(bin_save)
            bf.flush()

    return bin_sound.flatten() if flat else bin_sound


def configure_sound_card(card=None, sounds=[], indexes=[], sample_rate=96):
    if card is None:
        card = SoundCardModule()
        close_card = True

    if sample_rate == 192 or sample_rate == 192000:
        sample_rate = SampleRate._192000HZ
    elif sample_rate == 96 or sample_rate == 96000:
        sample_rate = SampleRate._96000HZ
    else:
        log.error(f"Sound sample rate {sample_rate} should be 96 or 192 (KHz)")
        raise (ValueError)

    if len(sounds) != len(indexes):
        log.error("Wrong number of sounds and indexes")
        raise (ValueError)

    sounds = [format_sound(s, flat=True) for s in sounds]
    for sound, index in zip(sounds, indexes):
        card.send_sound(sound, index, sample_rate, DataType.INT32)

    if close_card:
        card.close()
    return


def sound_sample_freq(soft_sound):
    if soft_sound == "sysdefault":
        return 44100
    elif soft_sound == "xonar":
        return 192000
    elif soft_sound is None:
        return 96000
    else:
        log.error("SOFT_SOUND in not: 'sysdefault', 'xonar' or 'None'")
        raise (NotImplementedError)


def init_sounds(sph, tone=True, noise=True):
    # TODO: remove creation of card objec when checks are implemented
    if sph.SOFT_SOUND is None:
        msg = f"""
    ##########################################
    SOUND BOARD NOT FOUND ON SYSTEM!!",
    PLEASE GO TO:
    iblrig_params/IBL/tasks/{sph.PYBPOD_PROTOCOL}/task_settings.py
    and set
        SOFT_SOUND = 'sysdefault' or 'xonar'
    ##########################################"""
        card = SoundCardModule()
        if not card.connected:
            log.error(msg)
            raise (NameError)

        chans = "stereo"
    else:
        chans = "L+TTL"

    if tone:
        sph.GO_TONE = make_sound(
            rate=sph.SOUND_SAMPLE_FREQ,
            frequency=sph.GO_TONE_FREQUENCY,
            duration=sph.GO_TONE_DURATION,
            amplitude=sph.GO_TONE_AMPLITUDE,
            fade=0.01,
            chans=chans,
        )
    if noise:
        sph.WHITE_NOISE = make_sound(
            rate=sph.SOUND_SAMPLE_FREQ,
            frequency=-1,
            duration=sph.WHITE_NOISE_DURATION,
            amplitude=sph.WHITE_NOISE_AMPLITUDE,
            fade=0.01,
            chans=chans,
        )
    return sph


# FIXME: in _passiveCW use SoundCardModule to give to this v instead of finding device yourself
def trigger_sc_sound(sound_idx, card=None):
    if card is None:
        card = SoundCardModule()
        close_card = True
    # [MessageType] [Length] [Address] [Port] [PayloadType] [Payload] [Checksum]
    # write=2 LEN=6 addr=32 port=255 payloadType=2 payload=[index 0]U16 checksum=43

    # 2 6 32 255 2 [2 0] 43 --> play tone
    # 2 6 32 255 2 [3 0] 44 --> play noise

    # 2 LEN=5 33 255 1 [index]U8 checksum

    def _calc_checksum(data):
        return sum(data) & 0xFF

    sound_idx = int(sound_idx)
    message = [2, 6, 32, 255, 2, sound_idx, 0]
    message.append(_calc_checksum(message))
    message = bytes(np.array(message, dtype=np.int8))
    # usb.write(port, message, timeout)
    card._dev.write(1, message, 200)

    if close_card:
        card.close()


if __name__ == "__main__":
    # # Generate sounds
    # device = 'xonar'
    # samplerate = sound_sample_freq(device)
    # sd = configure_sounddevice(output=device, samplerate=samplerate)
    # sd.stop()
    # rig_tone = make_sound(rate=samplerate, frequency=5000,
    #                       duration=10, amplitude=0.1)
    # rig_noise = make_sound(rate=samplerate, frequency=-
    #                        1, duration=10, amplitude=0.1)
    # N_TTL = make_sound(chans='L+TTL', amplitude=-1)
    # import matplotlib.pyplot as plt
    # # sd.play(rig_tone, samplerate, mapping=[1, 2])
    # bla = 0.5
    # c = make_chirp(f0=80, f1=160, length=bla, amp=0.1, fade=0.05, sf=192000)
    # plt.plot(np.linspace(0, bla, 192000), c[:, 0])
    # plt.show()

    # TEST SOUNDCARD MODULE
    card = SoundCardModule()
    SOFT_SOUND = None
    SOUND_SAMPLE_FREQ = sound_sample_freq(SOFT_SOUND)
    SOUND_BOARD_BPOD_PORT = "Serial3"
    WHITE_NOISE_DURATION = float(0.5)
    WHITE_NOISE_AMPLITUDE = float(0.05)
    GO_TONE_DURATION = float(0.1)
    GO_TONE_FREQUENCY = int(5000)
    GO_TONE_AMPLITUDE = float(0.0151)  # 0.0151 for 70.0 dB SPL CCU | 0.0272 for 70.0 dB SPL Xonar
    GO_TONE = make_sound(
        rate=SOUND_SAMPLE_FREQ,
        frequency=GO_TONE_FREQUENCY,
        duration=GO_TONE_DURATION,
        amplitude=GO_TONE_AMPLITUDE,
        fade=0.01,
        chans="stereo",
    )
    WHITE_NOISE = make_sound(
        rate=SOUND_SAMPLE_FREQ,
        frequency=-1,
        duration=WHITE_NOISE_DURATION,
        amplitude=WHITE_NOISE_AMPLITUDE,
        fade=0.01,
        chans="stereo",
    )
    GO_TONE_IDX = 2
    WHITE_NOISE_IDX = 4

    wave_int = format_sound(GO_TONE, flat=True)
    noise_int = format_sound(WHITE_NOISE, flat=True)

    card = SoundCardModule()
    card.send_sound(wave_int, GO_TONE_IDX, SampleRate._96000HZ, DataType.INT32)
    card.send_sound(noise_int, WHITE_NOISE_IDX, SampleRate._96000HZ, DataType.INT32)

    print("i")
