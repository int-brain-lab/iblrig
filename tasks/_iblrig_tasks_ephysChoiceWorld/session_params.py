#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
import os
import sys
from sys import platform
from pathlib import Path
import logging

from pythonosc import udp_client

from ibllib.graphic import numinput, multi_input
sys.path.append(str(Path(__file__).parent.parent))  # noqa
sys.path.append(str(Path(__file__).parent.parent.parent.parent))  # noqa
import adaptive
import ambient_sensor
import bonsai
import iotasks
import misc
import sound
from path_helper import SessionPathCreator
from rotary_encoder import MyRotaryEncoder
log = logging.getLogger('iblrig')


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings, debug=False, fmake=True):
        self.DEBUG = debug
        make = True
        self.IBLRIG_FOLDER = 'C:\\iblrig'
        self.IBLRIG_DATA_FOLDER = None  # ..\\iblrig_data if None
        # =====================================================================
        # IMPORT task_settings, user_settings, and SessionPathCreator params
        # =====================================================================
        ts = {i: task_settings.__dict__[i]
              for i in [x for x in dir(task_settings) if '__' not in x]}
        self.__dict__.update(ts)
        us = {i: user_settings.__dict__[i]
              for i in [x for x in dir(user_settings) if '__' not in x]}
        self.__dict__.update(us)
        self = iotasks.deserialize_pybpod_user_settings(self)
        spc = SessionPathCreator(self.IBLRIG_FOLDER, self.IBLRIG_DATA_FOLDER,
                                 self.PYBPOD_SUBJECTS[0],
                                 protocol=self.PYBPOD_PROTOCOL,
                                 board=self.PYBPOD_BOARD, make=make)
        self.__dict__.update(spc.__dict__)
        # =====================================================================
        # SETTINGS
        # =====================================================================
        self.RECORD_SOUND = True
        self.RECORD_AMBIENT_SENSOR_DATA = True
        self.RECORD_VIDEO = True
        self.OPEN_CAMERA_VIEW = True  # Always True if RECORD_VIDEO is True

        self.NTRIALS = 2000  # Number of trials for the current session
        self.USE_AUTOMATIC_STOPPING_CRITERIONS = True  # Weather to check for the Automatic stopping criterions or not  # noqa
        self.REPEAT_ON_ERROR = False  # not used
        self.INTERACTIVE_DELAY = 0.0
        self.RESPONSE_WINDOW = 60
        self.ITI_CORRECT = 1
        self.ITI_ERROR = 2
        self.CONTRAST_SET = [1., 0.25, 0.125, 0.0625, 0.]  # Full contrast set
        self.CONTRAST_SET_PROBABILITY_TYPE = 'biased'
        self.STIM_FREQ = 0.10  # Probably constant - NOT IN USE
        self.STIM_ANGLE = 0.  # Vertical orientation of Gabor patch
        self.STIM_SIGMA = 7.  # (azimuth_degree) Size of Gabor patch
        self.STIM_GAIN = 4.  # (azimuth_degree/mm) Gain of the RE
        # =====================================================================
        # SUBJECT
        # =====================================================================
        self.SUBJECT_WEIGHT = self.get_subject_weight()
        self.POOP_COUNT = True
        # =====================================================================
        # OSC CLIENT
        # =====================================================================
        self.OSC_CLIENT_PORT = 7110
        self.OSC_CLIENT_IP = '127.0.0.1'
        self.OSC_CLIENT = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP,
                                                     self.OSC_CLIENT_PORT)
        # =====================================================================
        # PREVIOUS DATA FILES
        # =====================================================================
        self.LAST_TRIAL_DATA = iotasks.load_data(self.PREVIOUS_SESSION_PATH)
        self.LAST_SETTINGS_DATA = iotasks.load_settings(
            self.PREVIOUS_SESSION_PATH)
        self.SESSION_ORDER = []
        self.SESSION_IDX = None
        self = iotasks.load_session_order_and_idx(self)
        # Load from file
        self.POSITIONS = None
        self.CONTRASTS = None
        self.QUIESCENT_PERIOD = None
        self.STIM_PHASE = None
        self.LEN_BLOCKS = None
        self = iotasks.load_session_pcqs(self)
        # =====================================================================
        # ADAPTIVE STUFF
        # =====================================================================
        self.AUTOMATIC_CALIBRATION = True
        self.CALIBRATION_VALUE = 0.067
        self.REWARD_AMOUNT = 3.
        self.REWARD_TYPE = 'Water 10% Sucrose'

        self.CALIB_FUNC = adaptive.init_calib_func(self)
        self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range(self)
        self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)

        # =====================================================================
        # ROTARY ENCODER
        # =====================================================================
        self.STIM_POSITIONS = [-35, 35]  # All possible positions (deg)
        self.QUIESCENCE_THRESHOLDS = [-2, 2]  # degree
        self.ALL_THRESHOLDS = (self.STIM_POSITIONS +
                               self.QUIESCENCE_THRESHOLDS)
        self.ROTARY_ENCODER = MyRotaryEncoder(self.ALL_THRESHOLDS,
                                              self.STIM_GAIN,
                                              self.COM['ROTARY_ENCODER'])
        # =====================================================================
        # SOUNDS
        # =====================================================================
        self.SOFT_SOUND = None
        self.SOUND_SAMPLE_FREQ = sound.sound_sample_freq(self.SOFT_SOUND)
        self.SOUND_BOARD_BPOD_PORT = 'Serial3'
        self.WHITE_NOISE_DURATION = float(0.5)
        self.WHITE_NOISE_AMPLITUDE = float(0.05)
        self.GO_TONE_DURATION = float(0.1)
        self.GO_TONE_FREQUENCY = int(5000)
        self.GO_TONE_AMPLITUDE = float(0.1)

        self.SD = sound.configure_sounddevice(
            output=self.SOFT_SOUND, samplerate=self.SOUND_SAMPLE_FREQ)
        # Create sounds and output actions of state machine
        self.GO_TONE = sound.make_sound(
            rate=self.SOUND_SAMPLE_FREQ, frequency=self.GO_TONE_FREQUENCY,
            duration=self.GO_TONE_DURATION, amplitude=self.GO_TONE_AMPLITUDE,
            fade=0.01, chans='stereo')
        self.WHITE_NOISE = sound.make_sound(
            rate=self.SOUND_SAMPLE_FREQ, frequency=-1,
            duration=self.WHITE_NOISE_DURATION,
            amplitude=self.WHITE_NOISE_AMPLITUDE, fade=0.01, chans='stereo')
        self.GO_TONE_IDX = 2
        self.WHITE_NOISE_IDX = 3
        sound.configure_sound_card(
            sounds=[self.GO_TONE, self.WHITE_NOISE],
            indexes=[self.GO_TONE_IDX, self.WHITE_NOISE_IDX],
            sample_rate=self.SOUND_SAMPLE_FREQ)
        # =====================================================================
        # VISUAL STIM
        # =====================================================================
        self.SYNC_SQUARE_X = 0.95
        self.SYNC_SQUARE_Y = 0.17
        self.USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
        self.BONSAI_EDITOR = False  # Open the Bonsai editor of visual stim
        bonsai.start_visual_stim(self)
        self.get_recording_site_data()
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        if not self.DEBUG:
            iotasks.save_session_settings(self)
            iotasks.copy_task_code(self)
            iotasks.save_task_code(self)
            self.bpod_lights(0)

        self.display_logs()

    # =========================================================================
    # METHODS
    # =========================================================================
    def get_recording_site_data(self):
        title = 'Recording site'
        fields = ['X (float):', 'Y (float):', 'Z (flaot):', 'D (float):',
                'Angle (10 or 20):', 'Origin (bregma or lambda):']
        defaults = [None, None, None, None, '10', 'bregma']
        types = [float, float, float, float, int, str]
        userdata = multi_input(
            title=title, add_fields=fields, defaults=defaults)
        try:
            out = [t(x) for x, t in zip(userdata, types)]
            self.REC_SITE = {'xyzd':out[:4], 'angle': out[4], 'origin': out[5]}
            return out
        except Exception:
            log.warning(
                f"One or more inputs are of the wrong type. Expected {types}")
            return self.get_recording_site_data()

    def save_ambient_sensor_reading(self, bpod_instance):
        return ambient_sensor.get_reading(bpod_instance,
                                          save_to=self.SESSION_RAW_DATA_FOLDER)

    def get_subject_weight(self):
        return numinput(
            "Subject weighing (gr)", f"{self.PYBPOD_SUBJECTS[0]} weight (gr):",
            nullable=False)

    def bpod_lights(self, command: int):
        fpath = Path(self.IBLRIG_PARAMS_FOLDER) / 'bpod_lights.py'
        os.system(f"python {fpath} {command}")

    def get_port_events(self, events, name=''):
        return misc.get_port_events(events, name=name)

    # =========================================================================
    # SOUND INTERFACE FOR STATE MACHINE
    # =========================================================================
    def play_tone(self):
        self.SD.play(self.GO_TONE, self.SOUND_SAMPLE_FREQ)

    def play_noise(self):
        self.SD.play(self.WHITE_NOISE, self.SOUND_SAMPLE_FREQ)

    def stop_sound(self):
        self.SD.stop()

    # =========================================================================
    # JSON ENCODER PATCHES
    # =========================================================================
    def reprJSON(self):
        def remove_from_dict(sx):
            if "weighings" in sx.keys():
                sx["weighings"] = None
            if "water_administration" in sx.keys():
                sx["water_administration"] = None
            return sx

        d = self.__dict__.copy()
        d['GO_TONE'] = 'go_tone(freq={}, dur={}, amp={})'.format(
            self.GO_TONE_FREQUENCY, self.GO_TONE_DURATION,
            self.GO_TONE_AMPLITUDE)
        d['WHITE_NOISE'] = 'white_noise(freq=-1, dur={}, amp={})'.format(
            self.WHITE_NOISE_DURATION, self.WHITE_NOISE_AMPLITUDE)
        d['SD'] = str(d['SD'])
        d['OSC_CLIENT'] = str(d['OSC_CLIENT'])
        d['SESSION_DATETIME'] = self.SESSION_DATETIME.isoformat()
        d['CALIB_FUNC'] = str(d['CALIB_FUNC'])
        d['CALIB_FUNC_RANGE'] = str(d['CALIB_FUNC_RANGE'])
        if isinstance(d['PYBPOD_SUBJECT_EXTRA'], list):
            sub = []
            for sx in d['PYBPOD_SUBJECT_EXTRA']:
                sub.append(remove_from_dict(sx))
            d['PYBPOD_SUBJECT_EXTRA'] = sub
        elif isinstance(d['PYBPOD_SUBJECT_EXTRA'], dict):
            d['PYBPOD_SUBJECT_EXTRA'] = remove_from_dict(
                d['PYBPOD_SUBJECT_EXTRA'])
        d['LAST_TRIAL_DATA'] = None
        d['LAST_SETTINGS_DATA'] = None
        d['POSITIONS'] = None
        d['CONTRASTS'] = None
        d['QUIESCENT_PERIOD'] = None
        d['STIM_PHASE'] = None
        d['LEN_BLOCKS'] = None

        return d

    def display_logs(self):
        if self.PREVIOUS_DATA_FILE:
            msg = f"""
##########################################
PREVIOUS SESSION FOUND
LOADING PARAMETERS FROM: {self.PREVIOUS_DATA_FILE}

PREVIOUS SESSION NUMBER: {self.LAST_SETTINGS_DATA['SESSION_IDX'] + 1}
PREVIOUS NTRIALS:        {self.LAST_TRIAL_DATA["trial_num"]}
PREVIOUS WATER DRANK:    {self.LAST_TRIAL_DATA['water_delivered']}
PREVIOUS WEIGHT:         {self.LAST_SETTINGS_DATA['SUBJECT_WEIGHT']}
##########################################"""
            log.info(msg)


if __name__ == '__main__':
    """
    SessionParamHandler fmake flag=False disables:
        making folders/files;
    SessionParamHandler debug flag disables:
        running auto calib;
        calling bonsai
        turning off lights of bpod board
    """
    import task_settings as _task_settings
    import scratch._user_settings as _user_settings
    import datetime
    dt = datetime.datetime.now()
    dt = [str(dt.year), str(dt.month), str(dt.day),
          str(dt.hour), str(dt.minute), str(dt.second)]
    dt = [x if int(x) >= 10 else '0' + x for x in dt]
    dt.insert(3, '-')
    _user_settings.PYBPOD_SESSION = ''.join(dt)
    _user_settings.PYBPOD_SETUP = 'biasedChoiceWorld'
    _user_settings.PYBPOD_PROTOCOL = '_iblrig_tasks_biasedChoiceWorld'
    if platform == 'linux':
        r = "/home/nico/Projects/IBL/github/iblrig"
        _task_settings.IBLRIG_FOLDER = r
        d = ("/home/nico/Projects/IBL/github/iblrig/scratch/" +
             "test_iblrig_data")
        _task_settings.IBLRIG_DATA_FOLDER = d
        _task_settings.AUTOMATIC_CALIBRATION = False
        _task_settings.USE_VISUAL_STIMULUS = False

    sph = SessionParamHandler(_task_settings, _user_settings,
                              debug=False, fmake=True)
    for k in sph.__dict__:
        if sph.__dict__[k] is None:
            print(f"{k}: {sph.__dict__[k]}")
    self = sph
    print("Done!")
