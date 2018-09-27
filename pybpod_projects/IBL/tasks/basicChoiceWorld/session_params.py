# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-07-12 16:18:59
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from sys import platform

import numpy as np
import scipy.stats as st
from dateutil import parser
from pythonosc import udp_client

from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


class Sounds():
    """Software solution for playing sounds"""
    def configure_sounddevice(sd=None):
        if sd is None:
            import sounddevice as sd

        devices = sd.query_devices()
        sd.default.device = [(i, d) for i, d in enumerate(
            devices) if 'Speakers' in d['name']][0][0]
        sd.default.latency = 'low'
        sd.default.channels = 8
        return sd

    def make_sound(frequency=10000, duration=0.1, amplitude=1, fade=0.01):
        """Build sound to feed to sounddevice lib.
        If frequency is set to -1 will produce white noise
        frequency  # Hz
        amplitude  # [0->1]
        """
        sample_rate = 44100  # sample rate, depend on the sound card
        tone_duration = duration  # sec
        fade_duration = fade  # sec

        tvec = np.linspace(0, tone_duration, tone_duration * sample_rate)
        tone = amplitude * np.sin(2 * np.pi * frequency * tvec)  # tone vec
        size = sample_rate * fade_duration / 2  #
        dist = st.expon(0., size)  # distribution object provided by scipy
        F = dist.cdf  # cumulative density function
        ker1 = F(range(int(sample_rate * tone_duration)))
        ker2 = ker1[::-1]
        ker = ker1 * ker2
        tone = tone * ker
        if frequency == -1:
            tone = amplitude * np.random.rand(tone.size)

        ttl = tone.copy()
        ttl[:] = 1.

        sound = np.array([tone, ttl]).T
        return sound


class MyRotaryEncoder(object):

    def __init__(self, all_thresholds, gain):
        self.all_thresholds = all_thresholds
        self.wheel_perim = 31 * 2 * np.pi  # = 194,778744523
        self.wheel_deg_mm = 360 / self.wheel_perim
        self.factor = self.wheel_deg_mm / gain
        self.SET_THRESHOLDS = [x * self.factor for x in self.all_thresholds]
        self.ENABLE_THRESHOLDS = [(True if x != 0
                                   else False) for x in self.SET_THRESHOLDS]
        # ENABLE_THRESHOLDS needs 8 bools even if only 2 thresholds are set
        while len(self.ENABLE_THRESHOLDS) < 8:
            self.ENABLE_THRESHOLDS.append(False)

    def reprJSON(self):
        d = self.__dict__
        return d


class session_param_handler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings):
        # =====================================================================
        # IMPORT task_settings AND user_settings
        # =====================================================================
        ts = {i: task_settings.__dict__[i]
              for i in [x for x in dir(task_settings) if '__' not in x]}
        self.__dict__.update(ts)
        us = {i: user_settings.__dict__[i]
              for i in [x for x in dir(user_settings) if '__' not in x]}
        self.__dict__.update(us)
        self.deserialize_session_user_settings()
        # =====================================================================
        # SOUNDS
        # =====================================================================
        self.GO_TONE = Sounds.make_sound(frequency=self.GO_TONE_FREQUENCY,
                                         duration=self.GO_TONE_DURATION,
                                         amplitude=self.GO_TONE_AMPLITUDE)
        self.WHITE_NOISE = Sounds.make_sound(
            frequency=-1,
            duration=self.WHITE_NOISE_DURATION,
            amplitude=self.WHITE_NOISE_AMPLITUDE)
        self.SD = Sounds.configure_sounddevice()
        # =====================================================================
        # OSC CLIENT
        # =====================================================================
        self.OSC_CLIENT = self._osc_client_init()
        # =====================================================================
        # ROTARY ENCODER
        # =====================================================================
        self.ALL_THRESHOLDS = (self.STIM_POSITIONS +
                               self.QUIESCENCE_THRESHOLDS)
        self.ROTARY_ENCODER = MyRotaryEncoder(self.ALL_THRESHOLDS,
                                              self.STIM_GAIN)
        # Names of the RE events generated by Bpod
        self.ENCODER_EVENTS = ['RotaryEncoder1_{}'.format(x) for x in
                               list(range(1, len(self.ALL_THRESHOLDS) + 1))]
        # Dict mapping threshold crossings with name ov RE event
        self.THRESHOLD_EVENTS = dict(zip(self.ALL_THRESHOLDS,
                                         self.ENCODER_EVENTS))
        if platform == 'linux':
            self.ROTARY_ENCODER_PORT = '/dev/ttyACM0'
        self._configure_rotary_encoder(RotaryEncoderModule)
        # =====================================================================
        # FOLDER STRUCTURE AND DATA FILES
        # =====================================================================
        if platform == 'linux':
            self.IBLRIG_FOLDER = '/home/nico/Projects/IBL/IBL-github/iblrig'
        else:
            self.IBLRIG_FOLDER = self._iblrig_folder_init()

        self.ROOT_DATA_FOLDER = self._root_data_folder(self.IBLRIG_FOLDER,
                                                       self.MAIN_DATA_FOLDER)
        self.VISUAL_STIM_FOLDER = os.path.join(self.IBLRIG_FOLDER,
                                               'visual_stim', 'Gabor2D')
        self.VISUAL_STIMULUS_FILE = os.path.join(self.IBLRIG_FOLDER,
                                                 'visual_stim', 'Gabor2D',
                                                 'Gabor2D.bonsai')
        self.SUBJECT_NAME = self.PYBPOD_SUBJECTS[0]
        self.SUBJECT_FOLDER = self.check_folder(self.ROOT_DATA_FOLDER,
                                                self.SUBJECT_NAME)
        self.SESSION_DATETIME = parser.parse(self.PYBPOD_SESSION)
        self.SESSION_DATE = self.SESSION_DATETIME.date().isoformat()
        self.SESSION_DATE_FOLDER = self.check_folder(self.SUBJECT_FOLDER,
                                                     self.SESSION_DATE)
        self.SESSION_NUMBER = self._session_number()
        self.SESSION_FOLDER = self.check_folder(self.SESSION_DATE_FOLDER,
                                                self.SESSION_NUMBER)
        self.SESSION_RAW_DATA_FOLDER = self.check_folder(self.SESSION_FOLDER,
                                                         'raw_behavior_data')
        self.SESSION_NAME = '{}'.format(os.path.sep).join([self.SUBJECT_NAME,
                                                           self.SESSION_DATE,
                                                           self.SESSION_NUMBER
                                                           ])
        self.BASE_FILENAME = '_ibl_task'
        self.SETTINGS_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                               self.BASE_FILENAME +
                                               '.settings.json')
        self.DATA_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                           self.BASE_FILENAME +
                                           '.data.jsonable')
        # =====================================================================
        # REWARD INITIALIZATION
        # =====================================================================
        self.PREVIOUS_DATA_FILE = self._previous_data_file()
        self.LAST_TRIAL_DATA = self._load_last_trial()
        self.REWARD_CURRENT = self._init_reward()
        # =====================================================================
        # RUN BONSAI
        # =====================================================================
        self._use_ibl_bonsai = True
        self.BONSAI = self.get_bonsai_path()
        self.run_bonsai()
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        self._save_session_settings()
        self._save_task_code()

    # =========================================================================
    # METHODS
    # =========================================================================
    # SERIALIZER
    # =========================================================================
    def reprJSON(self):
        d = self.__dict__.copy()
        d['GO_TONE'] = 'go_tone(freq={}, dur={}, amp={})'.format(
            self.GO_TONE_FREQUENCY, self.GO_TONE_DURATION,
            self.GO_TONE_AMPLITUDE)
        d['WHITE_NOISE'] = 'white_noise(freq=-1, dur={}, amp={})'.format(
            self.WHITE_NOISE_DURATION, self.WHITE_NOISE_AMPLITUDE)
        d['SD'] = str(d['SD'])
        d['OSC_CLIENT'] = str(d['OSC_CLIENT'])
        d['SESSION_DATETIME'] = str(self.SESSION_DATETIME)
        return d

    # =========================================================================
    # FILES AND FOLDER STRUCTURE
    # =========================================================================
    def get_bonsai_path(self):
        """Checks for Bonsai folder in iblrig.
        Returns string with bonsai executable path."""
        folders = self.get_subfolder_paths(self.IBLRIG_FOLDER)
        bonsai_folder = [x for x in folders if 'Bonsai' in x][0]
        ibl_bonsai = os.path.join(bonsai_folder, 'Bonsai64.exe')

        preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai64.exe"
        if self._use_ibl_bonsai == True:
            BONSAI = ibl_bonsai
        elif self._use_ibl_bonsai == False and preexisting_bonsai.exists():
            BONSAI = str(preexisting_bonsai)
        elif self._use_ibl_bonsai == False and not preexisting_bonsai.exists():
            print("NOT FOUND: {}\n Using packaged Bonsai.".format(
                str(preexisting_bonsai)))
            BONSAI = ibl_bonsai
        return BONSAI

    def run_bonsai(self):
        if self.USE_VISUAL_STIMULUS and self.BONSAI:
            # Copy stimulus folder with bonsai workflow
            src = self.VISUAL_STIM_FOLDER
            dst = os.path.join(self.SESSION_RAW_DATA_FOLDER, 'Gabor2D/')
            shutil.copytree(src, dst)
            # Run Bonsai workflow
            here = os.getcwd()
            os.chdir(os.path.join(self.IBLRIG_FOLDER, 'visual_stim',
                                  'Gabor2D'))
            bns = self.BONSAI
            wkfl = self.VISUAL_STIMULUS_FILE

            pos = "-p:FileNamePositions=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_ibl_encoderPositions.bonsai_raw.ssv")
            evt = "-p:FileNameEvents=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_ibl_encoderEvents.bonsai_raw.ssv")
            itr = "-p:FileNameTrialInfo=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_ibl_encoderTrialInfo.bonsai_raw.ssv")
            com = "-p:REPortName=" + self.ROTARY_ENCODER_PORT
            mic = "-p:FileNameMic=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER, "_ibl_rawMic.data.wav")
            rec = "-p:RecordSound=" + str(self.RECORD_SOUND)

            start = '--start'
            noeditor = '--noeditor'

            if self.BONSAI_EDITOR:
                bonsai = subprocess.Popen(
                    [bns, wkfl, start, pos, evt, itr, com, mic, rec])
            elif not self.BONSAI_EDITOR:
                bonsai = subprocess.Popen(
                    [bns, wkfl, noeditor, pos, evt, itr, com, mic, rec])
            time.sleep(5)
            bonsai
            os.chdir(here)
        else:
            self.USE_VISUAL_STIMULUS = False

    @staticmethod
    def check_folder(str1, str2=None):
        """Check if folder path exists and if not create it."""
        if str2 is not None:
            f = os.path.join(str1, str2)
        else:
            f = str1
        if not os.path.exists(f):
            os.mkdir(f)
        return f

    def _iblrig_folder_init(self):
        if '/' in self.IBLRIG_FOLDER:
            p = '{}'.format(os.path.sep).join(self.IBLRIG_FOLDER.split('/'))
        elif '\\' in self.IBLRIG_FOLDER:
            p = '{}'.format(os.path.sep).join(self.IBLRIG_FOLDER.split('\\'))
        return p

    def _root_data_folder(self, iblrig_folder, main_data_folder):
        if main_data_folder is None:
            try:
                os.path.exists(iblrig_folder)
                out = os.path.join(iblrig_folder, 'Subjects')
                out = self.check_folder(out)
                return out
            except IOError as e:
                print(e, "\nCouldn't find IBLRIG_FOLDER in file system\n")
        else:
            return main_data_folder

    def _session_number(self):
        session_nums = [int(x) for x in os.listdir(self.SESSION_DATE_FOLDER)
                        if os.path.isdir(os.path.join(self.SESSION_DATE_FOLDER,
                                                      x))]
        if not session_nums:
            out = str(1)
        else:
            out = str(int(max(session_nums)) + 1)

        return out

    @staticmethod
    def get_subfolder_paths(folder):
        out = [os.path.join(folder, x) for x in os.listdir(folder)
               if os.path.isdir(os.path.join(folder, x))]
        return out

    def _previous_session_folders(self):
        """
        """
        session_folders = []
        for date in self.get_subfolder_paths(self.SUBJECT_FOLDER):
            session_folders.extend(self.get_subfolder_paths(date))

        session_folders = [x for x in sorted(session_folders)
                           if self.SESSION_FOLDER not in x]
        return session_folders

    def _previous_data_files(self):
        prev_data_files = []
        for prev_sess_path in self._previous_session_folders():
            prev_sess_path = os.path.join(prev_sess_path, 'raw_behavior_data')
            if self.BASE_FILENAME + '.data' in ''.join(os.listdir(
                                                       prev_sess_path)):
                prev_data_files.extend(os.path.join(prev_sess_path, x) for x
                                       in os.listdir(prev_sess_path) if
                                       self.BASE_FILENAME + '.data' in x)

        return prev_data_files

    def _previous_data_file(self):
        out = sorted(self._previous_data_files())
        if out:
            return out[-1]
        else:
            return None

    def _load_last_trial(self, i=-1):
        if self.PREVIOUS_DATA_FILE is None:
            return
        trial_data = []
        with open(self.PREVIOUS_DATA_FILE, 'r') as f:
            for line in f:
                last_trial = json.loads(line)
                trial_data.append(last_trial)
        return trial_data[i] if trial_data else None

    # =========================================================================
    # REWARD
    # =========================================================================
    def _init_reward(self):
        if self.LAST_TRIAL_DATA is None:
            return self.REWARD_INIT_VALUE
        else:
            try:
                out = (self.LAST_TRIAL_DATA['reward_valve_time'] /
                       self.LAST_TRIAL_DATA['reward_calibration'])
            except IOError:
                out = (self.LAST_TRIAL_DATA['reward_valve_time'] /
                       self.CALIBRATION_VALUE)
            return out

    # =========================================================================
    # OSC CLIENT
    # =========================================================================
    def _osc_client_init(self):
        osc_client = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP,
                                                self.OSC_CLIENT_PORT)
        return osc_client

    # =========================================================================
    # PYBPOD USER SETTINGS DESERIALIZATION
    # =========================================================================
    def deserialize_session_user_settings(self):
        self.PYBPOD_CREATOR = json.loads(self.PYBPOD_CREATOR)
        self.PYBPOD_USER_EXTRA = json.loads(self.PYBPOD_USER_EXTRA)

        self.PYBPOD_SUBJECTS = [json.loads(x.replace("'", '"'))
                                for x in self.PYBPOD_SUBJECTS]
        if len(self.PYBPOD_SUBJECTS) == 1:
            self.PYBPOD_SUBJECTS = self.PYBPOD_SUBJECTS[0]
        else:
            print("ERROR: Multiple subjects found in PYBPOD_SUBJECTS")
            raise IOError

        self.PYBPOD_SUBJECT_EXTRA = [json.loads(x) for x in
                                     self.PYBPOD_SUBJECT_EXTRA[1:-1
                                                               ].split('","')]
        if len(self.PYBPOD_SUBJECT_EXTRA) == 1:
            self.PYBPOD_SUBJECT_EXTRA = self.PYBPOD_SUBJECT_EXTRA[0]

    # =========================================================================
    # SERIALIZE AND SAVE
    # =========================================================================
    def _save_session_settings(self):
        with open(self.SETTINGS_FILE_PATH, 'a') as f:
            f.write(json.dumps(self, cls=ComplexEncoder))
            f.write('\n')
        return

    def _save_task_code(self):
        # Copy behavioral task python code
        src = os.path.join(self.IBLRIG_FOLDER, 'pybpod_projects', 'IBL',
                           'tasks', self.PYBPOD_PROTOCOL)
        dst = os.path.join(self.SESSION_RAW_DATA_FOLDER, self.PYBPOD_PROTOCOL)
        shutil.copytree(src, dst)
        # zip all existing folders
        # Should be the task code folder and if available stimulus code folder
        folders_to_zip = [os.path.join(self.SESSION_RAW_DATA_FOLDER, x)
                          for x in os.listdir(self.SESSION_RAW_DATA_FOLDER)
                          if os.path.isdir(os.path.join(
                              self.SESSION_RAW_DATA_FOLDER, x))]
        session_param_handler.zipit(
            folders_to_zip, os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                         '_ibl_code.files.zip'))

        [shutil.rmtree(x) for x in folders_to_zip]

    @staticmethod
    def zipdir(path, ziph):
        # ziph is zipfile handle
        for root, dirs, files in os.walk(path):
            for file in files:
                ziph.write(os.path.join(root, file),
                           os.path.relpath(os.path.join(root, file),
                                           os.path.join(path, '..')))

    @staticmethod
    def zipit(dir_list, zip_name):
        zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        for dir in dir_list:
            session_param_handler.zipdir(dir, zipf)
        zipf.close()

    def _configure_rotary_encoder(self, RotaryEncoderModule):
        m = RotaryEncoderModule(self.ROTARY_ENCODER_PORT)
        m.set_zero_position()  # Not necessarily needed
        m.set_thresholds(self.ROTARY_ENCODER.SET_THRESHOLDS)
        m.enable_thresholds(self.ROTARY_ENCODER.ENABLE_THRESHOLDS)
        m.close()

    # =========================================================================
    # PUBLIC SOUND METHODS
    # =========================================================================
    def play_tone(self):
        self.SD.play(self.GO_TONE, self.SOUND_SAMPLE_FREQ, mapping=[1, 2])

    def play_noise(self):
        self.SD.play(self.WHITE_NOISE, self.SOUND_SAMPLE_FREQ, mapping=[1, 2])

    def stop_sound(self):
        self.SD.stop()


if __name__ == '__main__':
    os.chdir(r'C:\iblrig\pybpod_projects\IBL\tasks\basicChoiceWorld')
    import task_settings as _task_settings
    import _user_settings
    sph = session_param_handler(_task_settings, _user_settings)
    self = sph
    print("Done!")
