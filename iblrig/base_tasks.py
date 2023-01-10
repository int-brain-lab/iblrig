"""
This module is intended to provide commonalities for all tasks.
Base classes for trial parameters and session parameters.
"""
from pathlib import Path
from abc import ABC
import datetime
import inspect
import logging
import os

import numpy as np
import yaml

from pythonosc import udp_client

import iblrig.adaptive as adaptive
import iblrig.path_helper
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


class ChoiceWorldTask(object):
    @property
    def elapsed_time(self):
        # elapsed time from init datetime in seconds
        return (datetime.datetime.now() - self.init_datetime).total_seconds()

    @property
    def signed_contrast(self):
        return self.contrast * np.sign(self.position)


class BaseSessionParamHandler(ABC):

    def __init__(self, debug=False):
        self.DEBUG = debug
        self.calibration = Bunch({})
        # Load pybpod settings
        self.pybpod_settings = iblrig.path_helper.load_pybpod_settings_yaml('pybpod_settings.yaml')
        # get another set of parameters from .iblrig_params.json
        self.hardware_settings = iblrig.path_helper.load_settings_yaml('hardware_settings.yaml')
        # Load the tasks settings
        with open(Path(inspect.getfile(self.__class__)).parent.joinpath('task_parameters.yaml')) as fp:
            self.task_params = Bunch(yaml.safe_load(fp))

    def bpod_lights(self, command: int):
        fpath = Path(self.IBLRIG_FOLDER) / "scripts" / "bpod_lights.py"
        os.system(f"python {fpath} {command}")

    def get_port_events(self, events, name=""):
        return misc.get_port_events(events, name=name)

    def patch_settings_file(self, patch):
        self.__dict__.update(patch)
        misc.patch_settings_file(self.SETTINGS_FILE_PATH, patch)


class OSCClient(udp_client.SimpleUDPClient):
    """
    Handles communication to Bonsai using an UDP Client
    OSC channels:
        USED:
        /t  -> (int)    trial number current
        /p  -> (int)    position of stimulus init for current trial
        /h  -> (float)  phase of gabor for current trial
        /c  -> (float)  contrast of stimulus for current trial
        /f  -> (float)  frequency of gabor patch for current trial
        /a  -> (float)  angle of gabor patch for current trial
        /g  -> (float)  gain of RE to visual stim displacement
        /s  -> (float)  sigma of the 2D gaussian of gabor
        /e  -> (int)    events transitions  USED BY SOFTCODE HANDLER FUNC
        /r  -> (int)    wheter to reverse the side contingencies (0, 1)
    """

    OSC_PROTOCOL = {
        'trial_num': '/t',
        'position': '/p',
        'stim_phase': '/h',
        'contrast': '/c',
        'stim_freq': '/f',
        'stim_angle': '/a',
        'stim_gain': '/g',
        'stim_sigma': '/s',
        'stim_reverse': '/r',
    }

    def __init__(self, ip=OSC_CLIENT_IP, port=OSC_CLIENT_PORT):
        super(OSCClient, self).__init__(ip, port)

    def send2bonsai(self, **kwargs):
        """
        :param see list of keys in OSC_PROTOCOL
        :return:
        """
        for k in kwargs:
            if k in self.OSC_PROTOCOL:
                # need to convert basic numpy types to low-level python type for
                # punch card generation OSC module, I might as well have written C code
                value = kwargs[k].item() if isinstance(kwargs[k], np.generic) else kwargs[k]
                self.send_message(self.OSC_PROTOCOL[k], value)


class AmbientSensorMixin:

    def save_ambient_sensor_reading(self, bpod_instance):
        return ambient_sensor.get_reading(bpod_instance, save_to=self.SESSION_RAW_DATA_FOLDER)


class Frame2TTLMixin:
    """
    Frame 2 TTL interface for state machine
    """
    def start(self):
        self.F2TTL_GET_AND_SET_THRESHOLDS = frame2TTL.get_and_set_thresholds()


class RotaryEncoderMixin:
    """
    Rotary encoder interface for state machine
    """
    def __init__(self, *args, **kwargs):
        super(RotaryEncoderMixin, self).__init__()
        self.device_rotary_encoder = MyRotaryEncoder(
            all_thresholds=self.task_params.STIM_POSITIONS + self.task_params.QUIESCENCE_THRESHOLDS,
            gain=self.task_params.STIM_GAIN,
            com=self.hardware_settings.device_rotary_encoder['COM_ROTARY_ENCODER'],
            connect=False
        )

    def start(self):
        self.device_rotary_encoder.connect()
        bonsai.start_visual_stim(self)


class CameraMixin:
    """
    Camera recording interface for state machine via bonsai
    """
    def start_camera_recording(self):
        if bonsai.launch_cameras():
            return bonsai.start_camera_recording(self)
        else:
            return bonsai.start_mic_recording(self)


class SoundMixin:
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
        self.device_sound = Bunch({})
        # TODO: this is task specific
        # self.device_sound.SOFT_SOUND = None if "ephys" in self.PYBPOD_BOARD else self.SOFT_SOUND

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


class ChoiceWorldSession(SoundMixin,
                         Frame2TTLMixin,
                         RotaryEncoderMixin,
                         CameraMixin,
                         AmbientSensorMixin,
                         BaseSessionParamHandler):

    def __init__(self, *args,  fmake=True, interactive=True, **kwargs):
        super(ChoiceWorldSession, self).__init__(*args, **kwargs)
        # Create the folder architecture and get the paths property updated
        if not fmake:
            make = False
        elif fmake and "ephys" in self.pybpod_settings.PYBPOD_BOARD:
            make = True  # True makes only raw_behavior_data folder
        else:
            make = ["video"]  # besides behavior which folders to creae
        spc = SessionPathCreator(
            self.pybpod_settings.PYBPOD_SUBJECTS[0],
            protocol=self.pybpod_settings.PYBPOD_PROTOCOL,
            make=make)
        self.paths = Bunch(spc.__dict__)
        # OSC client
        self.osc_client = OSCClient()
        # Session data
        if interactive:
            self.SUBJECT_WEIGHT = user.ask_subject_weight(self.pybpod_settings.PYBPOD_SUBJECTS[0])
        else:
            self.SUBJECT_WEIGHT = np.NaN
        self.display_logs()

    @property
    def iti_reward(self, assert_calibration=True):
        """
        Returns the ITI time that needs to be set in order to achieve the desired ITI,
        by subtracting the time it takes to give a reward from the desired ITI.
        """
        if assert_calibration:
            assert 'REWARD_VALVE_TIME' in self.calibration.keys(), 'Reward valve time not calibrated'
        return self.task_params.ITI_CORRECT - self.calibration.get('REWARD_VALVE_TIME', None)

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
            self.task_params.GO_TONE_FREQUENCY,
            self.task_params.GO_TONE_DURATION,
            self.task_params.GO_TONE_AMPLITUDE
        )
        d["WHITE_NOISE"] = "white_noise(freq=-1, dur={}, amp={})".format(
            self.task_params.WHITE_NOISE_DURATION,
            self.task_params.WHITE_NOISE_AMPLITUDE
        )

        d["SD"] = str(d.get('SD', None))
        d["CALIB_FUNC"] = str(d.get('CALIB_FUNC', None))

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

    def checklist(self):
        """
        Before starting the task, this goes through a checklist making sure that the rig
        has calibration values and the hardware is connected
        :return:
        """
        # =====================================================================
        # ADAPTIVE STUFF - CALIBRATION OF THE WATER REWARD
        # =====================================================================
        self.CALIB_FUNC = None
        if self.task_params.AUTOMATIC_CALIBRATION:
            self.CALIB_FUNC = adaptive.init_calib_func()
        self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range()
        self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)
        # =====================================================================

    def start(self):
        # SUBJECT
        # =====================================================================
        self.SUBJECT_DISENGAGED_TRIGGERED = False
        self.SUBJECT_DISENGAGED_TRIALNUM = None
        self.SUBJECT_PROJECT = None  # user.ask_project(self.PYBPOD_SUBJECTS[0])
        # =====================================================================
        # PREVIOUS DATA FILES
        # =====================================================================
        self.LAST_TRIAL_DATA = iotasks.load_data(self.paths.PREVIOUS_SESSION_PATH)
        self.LAST_SETTINGS_DATA = iotasks.load_settings(self.paths.PREVIOUS_SESSION_PATH)
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        if not self.DEBUG:
            iotasks.save_session_settings(self)
            iotasks.copy_task_code(self)
            iotasks.save_task_code(self)
            if "ephys" not in self.PYBPOD_BOARD:
                iotasks.copy_video_code(self)
                iotasks.save_video_code(self)
            self.bpod_lights(0)
