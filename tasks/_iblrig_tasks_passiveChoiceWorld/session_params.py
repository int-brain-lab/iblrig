#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
import logging
import os
import tkinter as tk
from pathlib import Path
from sys import platform
from tkinter import messagebox

from pythonosc import udp_client

import iblrig.adaptive as adaptive
import iblrig.ambient_sensor as ambient_sensor
import iblrig.iotasks as iotasks
import iblrig.misc as misc
import iblrig.sound as sound
import iblrig.path_helper as ph

log = logging.getLogger("iblrig")
log.setLevel(logging.DEBUG)


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings, debug=False, fmake=True):
        self.DEBUG = debug
        make = True
        # =====================================================================
        # IMPORT task_settings, user_settings, and SessionPathCreator params
        # =====================================================================
        ts = {
            i: task_settings.__dict__[i] for i in [x for x in dir(task_settings) if "__" not in x]
        }
        self.__dict__.update(ts)
        us = {
            i: user_settings.__dict__[i] for i in [x for x in dir(user_settings) if "__" not in x]
        }
        self.__dict__.update(us)
        self = iotasks.deserialize_pybpod_user_settings(self)
        # Pretend to run a new ephys session
        spc = ph.SessionPathCreator(
            self.PYBPOD_SUBJECTS[0],
            protocol="_iblrig_tasks_ephysChoiceWorld",
            make=False,
        )  # don't make any folders
        # Get previous session folder i.e. the ephys session that just ran
        self.CORRESPONDING_EPHYS_SESSION = spc.PREVIOUS_SESSION_PATH
        # Load its metadata
        self.CORRESPONDING_EPHYS_SETTINGS_DATA = iotasks.load_settings(
            self.CORRESPONDING_EPHYS_SESSION
        )
        if self.CORRESPONDING_EPHYS_SETTINGS_DATA is None:
            self.CORRESPONDING_EPHYS_SETTINGS_DATA = {}
        # Get the vis stim file for an ephys session for the replay later
        self.VISUAL_STIMULUS_FILE_EPHYS = spc.VISUAL_STIMULUS_FILE
        # Patch the dict if no IS_MOCK key is found
        if "IS_MOCK" not in self.CORRESPONDING_EPHYS_SETTINGS_DATA.keys():
            self.CORRESPONDING_EPHYS_SETTINGS_DATA.update({"IS_MOCK": False})
        # run spc normally
        spc = ph.SessionPathCreator(
            self.PYBPOD_SUBJECTS[0], protocol=self.PYBPOD_PROTOCOL, make=make
        )
        self.__dict__.update(spc.__dict__)
        # =====================================================================
        # SETTINGS
        # =====================================================================
        self.RECORD_SOUND = True
        self.RECORD_AMBIENT_SENSOR_DATA = True

        self.NTRIALS = 300  # Number of trials for the current session
        self.USE_AUTOMATIC_STOPPING_CRITERIONS = (
            None  # Weather to check for the Automatic stopping criterions or not  # noqa
        )
        self.REPEAT_ON_ERROR = False  # not used
        self.INTERACTIVE_DELAY = 0.0
        self.RESPONSE_WINDOW = 60
        self.ITI_CORRECT = 1
        self.ITI_ERROR = 2
        self.CONTRAST_SET = [1.0, 0.25, 0.125, 0.0625, 0.0]  # Full contrast set
        self.CONTRAST_SET_PROBABILITY_TYPE = "biased"
        self.STIM_FREQ = 0.10  # Probably constant - NOT IN USE
        self.STIM_ANGLE = 0.0  # Vertical orientation of Gabor patch
        self.STIM_SIGMA = 7.0  # (azimuth_degree) Size of Gabor patch
        self.STIM_GAIN = 4.0  # (azimuth_degree/mm) Gain of the RE
        # =====================================================================
        # SUBJECT
        # =====================================================================
        # self.SUBJECT_WEIGHT = self.ask_subject_weight()
        self.POOP_COUNT = True
        self.SUBJECT_DISENGAGED_TRIGGERED = False
        self.SUBJECT_DISENGAGED_TRIALNUM = None
        # =====================================================================
        # OSC CLIENT
        # =====================================================================
        self.OSC_CLIENT_IP = "127.0.0.1"
        self.OSC_CLIENT_PORT = 7110
        self.OSC_CLIENT = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP, self.OSC_CLIENT_PORT)
        # =====================================================================
        # PREVIOUS DATA FILES
        # =====================================================================
        # Not used
        self.LAST_TRIAL_DATA = None  # iotasks.load_data(self.PREVIOUS_SESSION_PATH)
        self.LAST_SETTINGS_DATA = None  # iotasks.load_settings(self.PREVIOUS_SESSION_PATH)
        # Change to False if mock has its own task
        self.IS_MOCK = self.CORRESPONDING_EPHYS_SETTINGS_DATA["IS_MOCK"]
        # Get pregenerated session num (the num in the filename! from corresponding ephys sesison)
        self.SESSION_ORDER = self.CORRESPONDING_EPHYS_SETTINGS_DATA["SESSION_ORDER"]
        self.SESSION_IDX = self.CORRESPONDING_EPHYS_SETTINGS_DATA["SESSION_IDX"]
        self.PREGENERATED_SESSION_NUM = self.CORRESPONDING_EPHYS_SETTINGS_DATA[
            "PREGENERATED_SESSION_NUM"
        ]
        # Load session from file
        (
            self.STIM_DELAYS,
            self.STIM_IDS,
        ) = iotasks.load_passive_session_delays_ids(self.PREGENERATED_SESSION_NUM)
        self.QUIESCENT_PERIOD = None
        self.LEN_BLOCKS = None
        (
            self.POSITIONS,
            self.CONTRASTS,
            self.STIM_PHASE,
        ) = iotasks.load_passive_session_pcs(self.PREGENERATED_SESSION_NUM)
        # =====================================================================
        # ADAPTIVE STUFF
        # =====================================================================
        self.AUTOMATIC_CALIBRATION = True
        self.CALIBRATION_VALUE = 0.067
        self.REWARD_AMOUNT = 1.5
        self.REWARD_TYPE = None

        self.CALIB_FUNC = None
        if self.AUTOMATIC_CALIBRATION:
            self.CALIB_FUNC = adaptive.init_calib_func()
        self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range()
        self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)

        # =====================================================================
        # ROTARY ENCODER
        # =====================================================================
        self.STIM_POSITIONS = [-35, 35]  # All possible positions (deg)
        self.QUIESCENCE_THRESHOLDS = [-2, 2]  # degree
        self.ALL_THRESHOLDS = self.STIM_POSITIONS + self.QUIESCENCE_THRESHOLDS
        self.ROTARY_ENCODER = None
        # =====================================================================
        # frame2TTL
        # =====================================================================
        self.F2TTL_GET_AND_SET_THRESHOLDS = None
        # =====================================================================
        # SOUNDS
        # =====================================================================
        self.SOFT_SOUND = None
        self.SOUND_SAMPLE_FREQ = sound.sound_sample_freq(self.SOFT_SOUND)
        self.SOUND_BOARD_BPOD_PORT = "Serial3"
        self.WHITE_NOISE_DURATION = float(0.5)
        self.WHITE_NOISE_AMPLITUDE = float(0.05)
        self.GO_TONE_DURATION = float(0.1)
        self.GO_TONE_FREQUENCY = int(5000)
        self.GO_TONE_AMPLITUDE = float(0.0151)  # 0.0151 for 70.0 dB SPL CCU

        self.SD = sound.configure_sounddevice(
            output=self.SOFT_SOUND, samplerate=self.SOUND_SAMPLE_FREQ
        )
        # Create sounds and output actions of state machine
        self.GO_TONE = sound.make_sound(
            rate=self.SOUND_SAMPLE_FREQ,
            frequency=self.GO_TONE_FREQUENCY,
            duration=self.GO_TONE_DURATION,
            amplitude=self.GO_TONE_AMPLITUDE,
            fade=0.01,
            chans="stereo",
        )
        self.WHITE_NOISE = sound.make_sound(
            rate=self.SOUND_SAMPLE_FREQ,
            frequency=-1,
            duration=self.WHITE_NOISE_DURATION,
            amplitude=self.WHITE_NOISE_AMPLITUDE,
            fade=0.01,
            chans="stereo",
        )
        self.GO_TONE_IDX = 2
        self.WHITE_NOISE_IDX = 3
        sound.configure_sound_card(
            sounds=[self.GO_TONE, self.WHITE_NOISE],
            indexes=[self.GO_TONE_IDX, self.WHITE_NOISE_IDX],
            sample_rate=self.SOUND_SAMPLE_FREQ,
        )
        self.OUT_TONE = ("SoftCode", 1) if self.SOFT_SOUND else ("Serial3", 6)
        self.OUT_NOISE = ("SoftCode", 2) if self.SOFT_SOUND else ("Serial3", 7)
        self.OUT_STOP_SOUND = ("SoftCode", 0) if self.SOFT_SOUND else ("Serial3", ord("X"))
        # =====================================================================
        # PROBES + WEIGHT
        # =====================================================================
        # form_data = -1
        # while form_data == -1:
        #     form_data = user_input.session_form(mouse_name=self.SUBJECT_NAME)
        self.SUBJECT_WEIGHT = None
        self.PROBE_DATA = None
        # =====================================================================
        # VISUAL STIM
        # =====================================================================
        self.SYNC_SQUARE_X = 1.33
        self.SYNC_SQUARE_Y = -1.03
        self.USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
        self.BONSAI_EDITOR = False  # Open the Bonsai editor of visual stim
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
    def patch_settings_file(self, patch):
        self.__dict__.update(patch)
        misc.patch_settings_file(self.SETTINGS_FILE_PATH, patch)

    def warn_ephys(self):
        title = "START EPHYS RECODING"
        msg = (
            "Please start recording in spikeglx then press OK\n"
            + "Behavior task will run after you start the bonsai workflow"
        )
        # from ibllib.graphic import popup
        # popup(title, msg)
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, msg)
        root.quit()

    def save_ambient_sensor_reading(self, bpod_instance):
        return ambient_sensor.get_reading(bpod_instance, save_to=self.SESSION_RAW_DATA_FOLDER)

    def bpod_lights(self, command: int):
        fpath = Path(self.IBLRIG_FOLDER) / "scripts" / "bpod_lights.py"
        os.system(f"python {fpath} {command}")

    def get_port_events(self, events, name=""):
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
        d["GO_TONE"] = "go_tone(freq={}, dur={}, amp={})".format(
            self.GO_TONE_FREQUENCY, self.GO_TONE_DURATION, self.GO_TONE_AMPLITUDE
        )
        d["WHITE_NOISE"] = "white_noise(freq=-1, dur={}, amp={})".format(
            self.WHITE_NOISE_DURATION, self.WHITE_NOISE_AMPLITUDE
        )
        d["SD"] = str(d["SD"])
        d["OSC_CLIENT"] = str(d["OSC_CLIENT"])
        d["CALIB_FUNC"] = str(d["CALIB_FUNC"])
        d["CALIB_FUNC_RANGE"] = str(d["CALIB_FUNC_RANGE"])
        if isinstance(d["PYBPOD_SUBJECT_EXTRA"], list):
            sub = []
            for sx in d["PYBPOD_SUBJECT_EXTRA"]:
                sub.append(remove_from_dict(sx))
            d["PYBPOD_SUBJECT_EXTRA"] = sub
        elif isinstance(d["PYBPOD_SUBJECT_EXTRA"], dict):
            d["PYBPOD_SUBJECT_EXTRA"] = remove_from_dict(d["PYBPOD_SUBJECT_EXTRA"])
        d["LAST_TRIAL_DATA"] = None
        d["LAST_SETTINGS_DATA"] = None
        d["POSITIONS"] = None
        d["CONTRASTS"] = None
        d["QUIESCENT_PERIOD"] = None
        d["STIM_PHASE"] = None
        d["LEN_BLOCKS"] = None
        d["STIM_DELAYS"] = d["STIM_DELAYS"].tolist()
        d["STIM_IDS"] = d["STIM_IDS"].tolist()

        return d

    def display_logs(self):
        if self.PREVIOUS_DATA_FILE:
            msg = f"""
##########################################
    CORRESPONDING EPHYS SESSION FOUND
LOADING PARAMETERS FROM: {self.CORRESPONDING_EPHYS_SESSION}
##########################################"""
            log.info(msg)


if __name__ == "__main__":
    """
    SessionParamHandler fmake flag=False disables:
        making folders/files;
    SessionParamHandler debug flag disables:
        running auto calib;
        calling bonsai
        turning off lights of bpod board
    """
    import task_settings as _task_settings
    import iblrig.fake_user_settings as _user_settings
    import datetime

    dt = datetime.datetime.now()
    dt = [
        str(dt.year),
        str(dt.month),
        str(dt.day),
        str(dt.hour),
        str(dt.minute),
        str(dt.second),
    ]
    dt = [x if int(x) >= 10 else "0" + x for x in dt]
    dt.insert(3, "-")
    _user_settings.PYBPOD_SESSION = "".join(dt)
    _user_settings.PYBPOD_SETUP = "passiveChoiceWorld"
    _user_settings.PYBPOD_PROTOCOL = "_iblrig_tasks_passiveChoiceWorld"
    if platform == "linux":
        _task_settings.AUTOMATIC_CALIBRATION = False
        _task_settings.USE_VISUAL_STIMULUS = False

    sph = SessionParamHandler(_task_settings, _user_settings, debug=False, fmake=True)
    for k in sph.__dict__:
        if sph.__dict__[k] is None:
            print(f"{k}: {sph.__dict__[k]}")
    self = sph
    print("Done!")
