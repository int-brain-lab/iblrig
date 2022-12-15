"""
This module is intended to provide commonalities for all tasks.
Base classes for trial parameters and session parameters.
"""
from pathlib import Path
from abc import ABC
import inspect
import logging
import sys
import os


import numpy as np
import yaml

from pythonosc import udp_client

from iblrig import params as pybpod_params
from iblrig.path_helper import SessionPathCreator
from iblrig.rotary_encoder import MyRotaryEncoder
from iblutil.util import Bunch
import iblrig.ambient_sensor as ambient_sensor
import iblrig.bonsai as bonsai
import iblrig.frame2TTL as frame2TTL
import iblrig.iotasks as iotasks
import iblrig.misc as misc
import iblrig.sound as sound
import iblrig.user_input as user


log = logging.getLogger("iblrig")

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
        pass

    def start(self):
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

    def __init__(self, *args,  rig_settings_yaml=None, fmake=True, interactive=True, **kwargs):
        super(ChoiceWorldSessionParamHandler, self).__init__(*args, **kwargs)
        # Load rig settings
        self.rig = iotasks.load_rig_settings_yaml(rig_settings_yaml)
        # Load the tasks settings
        with open(Path(inspect.getfile(self.__class__)).parent.joinpath('task_settings.yml')) as fp:
            self.task = Bunch(yaml.safe_load(fp))
        # Create the folder architecture and get the paths property updated
        # Path handling
        if not fmake:
            make = False
        elif fmake and "ephys" in self.rig.PYBPOD_BOARD:
            make = True  # True makes only raw_behavior_data folder
        else:
            make = ["video"]  # besides behavior which folders to creae
        spc = SessionPathCreator(self.rig.PYBPOD_SUBJECTS[0], protocol=self.rig.PYBPOD_PROTOCOL, make=make)
        self.paths = Bunch(spc.__dict__)
        # get another set of parameters from .iblrig_params.json
        self.PARAMS = pybpod_params.load_params_file()
        # OSC client
        self.osc_client = udp_client.SimpleUDPClient(OSC_CLIENT_IP, OSC_CLIENT_PORT)
        # Session data
        if interactive:
            self.SUBJECT_WEIGHT = user.ask_subject_weight(self.rig.PYBPOD_SUBJECTS[0])
        else:
            self.SUBJECT_WEIGHT = np.NaN
        self.display_logs()

    def reprJSON(self):
        """
        JSON representation of the session parameters - one way street
        :return:
        """
        def remove_from_dict(sx):
            if "weighings" in sx.keys():
                sx["weighings"] = None
            if "water_administration" in sx.keys():
                sx["water_administration"] = None
            return sx

        d = self.__dict__.copy()
        d["GO_TONE"] = "go_tone(freq={}, dur={}, amp={})".format(
            self.GO_TONE_FREQUENCY, self.GO_TONE_DURATION, self.GO_TONE_AMPLITUDE
        )
        d["WHITE_NOISE"] = "white_noise(freq=-1, dur={}, amp={})".format(
            self.WHITE_NOISE_DURATION, self.WHITE_NOISE_AMPLITUDE
        )
        d["SD"] = str(d["SD"])
        d["OSC_CLIENT"] = str(d["OSC_CLIENT"])
        d["CALIB_FUNC"] = str(d["CALIB_FUNC"])
        if isinstance(d["PYBPOD_SUBJECT_EXTRA"], list):
            sub = []
            for sx in d["PYBPOD_SUBJECT_EXTRA"]:
                sub.append(remove_from_dict(sx))
            d["PYBPOD_SUBJECT_EXTRA"] = sub
        elif isinstance(d["PYBPOD_SUBJECT_EXTRA"], dict):
            d["PYBPOD_SUBJECT_EXTRA"] = remove_from_dict(d["PYBPOD_SUBJECT_EXTRA"])
        d["LAST_TRIAL_DATA"] = None
        d["LAST_SETTINGS_DATA"] = None
        return d

    def display_logs(self):
        if self.paths.PREVIOUS_DATA_FILE:
            msg = f"""
##########################################
PREVIOUS SESSION FOUND
LOADING PARAMETERS FROM:       {self.PREVIOUS_DATA_FILE}
PREVIOUS NTRIALS:              {self.LAST_TRIAL_DATA["trial_num"]}
PREVIOUS WATER DRANK:          {self.LAST_TRIAL_DATA["water_delivered"]}
LAST REWARD:                   {self.LAST_TRIAL_DATA["reward_amount"]}
LAST GAIN:                     {self.LAST_TRIAL_DATA["stim_gain"]}
PREVIOUS WEIGHT:               {self.LAST_SETTINGS_DATA["SUBJECT_WEIGHT"]}
##########################################"""
            log.info(msg)
