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

from ibllib.graphic import numinput
sys.path.append(str(Path(__file__).parent.parent))  # noqa
sys.path.append(str(Path(__file__).parent.parent.parent.parent))  # noqa
import adaptive
import ambient_sensor
import bonsai
import iotasks
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
        make = False if not fmake else ['video']
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
        # SUBJECT
        # =====================================================================
        self.SUBJECT_WEIGHT = self.get_subject_weight()
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
        # =====================================================================
        # ADAPTIVE STUFF
        # =====================================================================
        self.REWARD_AMOUNT = adaptive.init_reward_amount(self)
        self.CALIB_FUNC = adaptive.init_calib_func(self)
        self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range(self)
        self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)
        self.STIM_GAIN = adaptive.init_stim_gain(self)
        self.IMPULSIVE_CONTROL = 'OFF'
        self = adaptive.impulsive_control(self)
        # =====================================================================
        # ROTARY ENCODER
        # =====================================================================
        self.ALL_THRESHOLDS = (self.STIM_POSITIONS +
                               self.QUIESCENCE_THRESHOLDS)
        self.ROTARY_ENCODER = MyRotaryEncoder(self.ALL_THRESHOLDS,
                                              self.STIM_GAIN,
                                              self.COM['ROTARY_ENCODER'])
        # =====================================================================
        # SOUNDS
        # =====================================================================
        self.SOUND_SAMPLE_FREQ = sound.sound_sample_freq(self.SOFT_SOUND)

        self.WHITE_NOISE_DURATION = float(self.WHITE_NOISE_DURATION)
        self.WHITE_NOISE_AMPLITUDE = float(self.WHITE_NOISE_AMPLITUDE)
        self.GO_TONE_DURATION = float(self.GO_TONE_DURATION)
        self.GO_TONE_FREQUENCY = int(self.GO_TONE_FREQUENCY)
        self.GO_TONE_AMPLITUDE = float(self.GO_TONE_AMPLITUDE)

        self.SD = sound.configure_sounddevice(
            output=self.SOFT_SOUND, samplerate=self.SOUND_SAMPLE_FREQ)
        # Create sounds and output actions of state machine
        self.UPLOADER_TOOL = None
        self.GO_TONE = None
        self.WHITE_NOISE = None
        self = sound.init_sounds(self)  # sets GO_TONE and WHITE_NOISE
        self.OUT_TONE = ('SoftCode', 1) if self.SOFT_SOUND else None
        self.OUT_NOISE = ('SoftCode', 2) if self.SOFT_SOUND else None
        # =====================================================================
        # RUN VISUAL STIM
        # =====================================================================
        bonsai.start_visual_stim(self)
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        if not self.DEBUG:
            iotasks.save_session_settings(self)
            iotasks.copy_task_code(self)
            iotasks.save_task_code(self)
            iotasks.copy_video_code(self)
            iotasks.save_video_code(self)
            self.bpod_lights(0)

        self.display_logs()

    # =========================================================================
    # METHODS
    # =========================================================================
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

    # Bonsai start camera called from main task file
    def start_camera_recording(self):
        return bonsai.start_camera_recording(self)

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
        if self.SOFT_SOUND:
            d['GO_TONE'] = 'go_tone(freq={}, dur={}, amp={})'.format(
                self.GO_TONE_FREQUENCY, self.GO_TONE_DURATION,
                self.GO_TONE_AMPLITUDE)
            d['WHITE_NOISE'] = 'white_noise(freq=-1, dur={}, amp={})'.format(
                self.WHITE_NOISE_DURATION, self.WHITE_NOISE_AMPLITUDE)
        d['SD'] = str(d['SD'])
        d['OSC_CLIENT'] = str(d['OSC_CLIENT'])
        d['SESSION_DATETIME'] = self.SESSION_DATETIME.isoformat()
        d['CALIB_FUNC'] = str(d['CALIB_FUNC'])
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

        return d

    def display_logs(self):
        if self.PREVIOUS_DATA_FILE:
            msg = f"""
##########################################
PREVIOUS SESSION FOUND
LOADING PARAMETERS FROM: {self.PREVIOUS_DATA_FILE}

PREVIOUS NTRIALS:              {self.LAST_TRIAL_DATA["trial_num"]}
PREVIOUS NTRIALS (no repeats): {self.LAST_TRIAL_DATA["non_rc_ntrials"]}
PREVIOUS WATER DRANK: {self.LAST_TRIAL_DATA['water_delivered']}
LAST REWARD:                   {self.LAST_TRIAL_DATA["reward_amount"]}
LAST GAIN:                     {self.LAST_TRIAL_DATA["stim_gain"]}
LAST CONTRAST SET:             {self.LAST_TRIAL_DATA["ac"]["contrast_set"]}
BUFFERS:                       {'loaded'}
PREVIOUS WEIGHT:               {self.LAST_SETTINGS_DATA['SUBJECT_WEIGHT']}
##########################################"""
            log.info(msg)

        msg = f"""
##########################################
ADAPTIVE VALUES FOR CURRENT SESSION

REWARD AMOUNT:      {self.REWARD_AMOUNT} µl
VALVE OPEN TIME:    {self.REWARD_VALVE_TIME} sec
GAIN:               {self.STIM_GAIN} azimuth_degree/mm
IMPULSIVE CONTROL   {self.IMPULSIVE_CONTROL}
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
