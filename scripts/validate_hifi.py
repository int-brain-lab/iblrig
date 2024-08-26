# Validate sound output of the Bpod HiFi Module across a range of configurations
#
# When running this script you should hear a series of identical beeps (500 ms, 440 Hz).
# Any distortion, crackling, pops etc could indicate an issue with the HiFi module.
#
# NOTE:    Adapt SERIAL_PORT according to the connected hardware.
# WARNING: Be careful when using headphones for testing - the sound-output could be very loud!

import logging
from time import sleep

import numpy as np

from iblrig.hifi import HiFi
from iblutil.util import setup_logger

setup_logger(name='iblrig', level='DEBUG')
log = logging.getLogger(__name__)

SERIAL_PORT = '/dev/ttyACM0'
DURATION_SEC = 0.5
PAUSE_SEC = 0.5
FREQUENCY_HZ = 480
FADE_SEC = 0.02

hifi = HiFi(SERIAL_PORT, attenuation_db=0)

for channels in ['mono', 'stereo']:
    for sampling_rate_hz in [44100, 48e3, 96e3, 192e3]:
        # create signal
        t = np.linspace(0, DURATION_SEC, int(sampling_rate_hz * DURATION_SEC), False)
        sound = np.sin(2 * np.pi * FREQUENCY_HZ * t) * 0.1

        # avoid pops by fading the signal in and out
        fade = np.linspace(0, 1, round(FADE_SEC * sampling_rate_hz))
        sound[: len(fade)] *= fade
        sound[-len(fade) :] *= np.flip(fade)

        # create stereo signal by duplication
        if channels == 'stereo':
            sound = sound.reshape(-1, 1).repeat(2, axis=1)

        # load & play sound
        hifi.sampling_rate_hz = sampling_rate_hz
        hifi.load(0, sound)
        hifi.push()
        hifi.play(0)

        # wait for next iteration
        sleep(DURATION_SEC + PAUSE_SEC)
