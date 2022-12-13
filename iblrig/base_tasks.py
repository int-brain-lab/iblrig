"""
This module is intended to provide commonalities for all tasks.
Base classes for trial parameters and session parameters.
"""
from pathlib import Path
from abc import ABC
import sys
import os
import yaml

from pythonosc import udp_client

import iblrig.bonsai as bonsai
import iblrig.frame2TTL as frame2TTL
import iblrig.iotasks as iotasks
from iblrig.path_helper import SessionPathCreator
from iblrig.rotary_encoder import MyRotaryEncoder
import iblrig.misc as misc
import iblrig.ambient_sensor as ambient_sensor
import iblrig.sound as sound

OSC_CLIENT_IP = "127.0.0.1"
OSC_CLIENT_PORT = 7110


class BaseSessionParamHandler(ABC):
    SESSION_START_DELAY_SEC = 0

    def __init__(self, debug=False):
        self.DEBUG = debug
        # =====================================================================
        # Load task_settings and user_settings
        # =====================================================================
        path_task = Path(sys.modules[self.__module__].__file__).parent
        with open(path_task.joinpath('task_settings.yaml')) as fp:
            ts = yaml.safe_load(fp) or {}
        with open(path_task.joinpath('user_settings.yaml')) as fp:
            us = yaml.safe_load(fp) or {}
        self.__dict__.update(ts)
        self.__dict__.update(us)

    def bpod_lights(self, command: int):
        fpath = Path(self.IBLRIG_FOLDER) / "scripts" / "bpod_lights.py"
        os.system(f"python {fpath} {command}")

    def get_port_events(self, events, name=""):
        return misc.get_port_events(events, name=name)

    def patch_settings_file(self, patch):
        self.__dict__.update(patch)
        misc.patch_settings_file(self.SETTINGS_FILE_PATH, patch)


class SessionParamHandlerAmbientSensorMixin:

    def save_ambient_sensor_reading(self, bpod_instance):
        return ambient_sensor.get_reading(bpod_instance, save_to=self.SESSION_RAW_DATA_FOLDER)


class SessionParamHandlerFrame2TTLMixin:
    """
    Frame 2 TTL interface for state machine
    """
    def __init__(self, *args, **kwargs):
        self.F2TTL_GET_AND_SET_THRESHOLDS = frame2TTL.get_and_set_thresholds()


class SessionParamHandlerRotaryEncoderMixin:
    """
    Sound interface methods for state machine
    """
    def __init__(self, *args, **kwargs):
        self.ALL_THRESHOLDS = self.STIM_POSITIONS + self.QUIESCENCE_THRESHOLDS
        self.ROTARY_ENCODER = MyRotaryEncoder(
            self.ALL_THRESHOLDS, self.STIM_GAIN, self.PARAMS["COM_ROTARY_ENCODER"]
        )

    def start(self):
        bonsai.start_visual_stim(self)


class SessionParamHandlerCameraMixin:
    """
    Camera recording interface for state machine via bonsai
    """
    def start_camera_recording(self):
        if bonsai.launch_cameras():
            return bonsai.start_camera_recording(self)
        else:
            return bonsai.start_mic_recording(self)


class SessionParamHandlerSoundMixin:
    """
    Sound interface methods for state machine
    """
    def play_tone(self):
        self.SD.play(self.GO_TONE, self.SOUND_SAMPLE_FREQ)

    def play_noise(self):
        self.SD.play(self.WHITE_NOISE, self.SOUND_SAMPLE_FREQ)

    def stop_sound(self):
        self.SD.stop()

    def init_sound_device(self):
        # =====================================================================
        # SOUNDS
        # =====================================================================
        self.SOFT_SOUND = None if "ephys" in self.PYBPOD_BOARD else self.SOFT_SOUND
        self.SOUND_SAMPLE_FREQ = sound.sound_sample_freq(self.SOFT_SOUND)

        self.WHITE_NOISE_DURATION = float(self.WHITE_NOISE_DURATION)
        self.WHITE_NOISE_AMPLITUDE = float(self.WHITE_NOISE_AMPLITUDE)
        self.GO_TONE_DURATION = float(self.GO_TONE_DURATION)
        self.GO_TONE_FREQUENCY = int(self.GO_TONE_FREQUENCY)
        self.GO_TONE_AMPLITUDE = float(self.GO_TONE_AMPLITUDE)

        self.SD = sound.configure_sounddevice(
            output=self.SOFT_SOUND, samplerate=self.SOUND_SAMPLE_FREQ
        )
        # Create sounds and output actions of state machine
        self.GO_TONE = None
        self.WHITE_NOISE = None
        self = sound.init_sounds(self)  # sets GO_TONE and WHITE_NOISE
        # SoundCard config params
        self.SOUND_BOARD_BPOD_PORT = "Serial3"
        self.GO_TONE_IDX = 2
        self.WHITE_NOISE_IDX = 3
        if self.SOFT_SOUND is None:
            sound.configure_sound_card(
                sounds=[self.GO_TONE, self.WHITE_NOISE],
                indexes=[self.GO_TONE_IDX, self.WHITE_NOISE_IDX],
                sample_rate=self.SOUND_SAMPLE_FREQ,
            )

        self.OUT_TONE = ("SoftCode", 1) if self.SOFT_SOUND else ("Serial3", 6)
        self.OUT_NOISE = ("SoftCode", 2) if self.SOFT_SOUND else ("Serial3", 7)
        self.OUT_STOP_SOUND = ("SoftCode", 0) if self.SOFT_SOUND else ("Serial3", ord("X"))


class ChoiceWorldSessionParamHandler(SessionParamHandlerSoundMixin,
                                     SessionParamHandlerFrame2TTLMixin,
                                     SessionParamHandlerRotaryEncoderMixin,
                                     SessionParamHandlerCameraMixin,
                                     SessionParamHandlerAmbientSensorMixin,
                                     BaseSessionParamHandler):

    def __init__(self, *args, fmake=True, **kwargs):
        super(ChoiceWorldSessionParamHandler, self).__init__(*args, **kwargs)
        # Path handling
        self = iotasks.deserialize_pybpod_user_settings(self)
        if not fmake:
            make = False
        elif fmake and "ephys" in self.PYBPOD_BOARD:
            make = True  # True makes only raw_behavior_data folder
        else:
            make = ["video"]  # besides behavior which folders to creae
        spc = SessionPathCreator(self.PYBPOD_SUBJECTS[0], protocol=self.PYBPOD_PROTOCOL, make=make)
        self.__dict__.update(spc.__dict__)

        # OSC client
        self.OSC_CLIENT = udp_client.SimpleUDPClient(OSC_CLIENT_IP, OSC_CLIENT_PORT)
