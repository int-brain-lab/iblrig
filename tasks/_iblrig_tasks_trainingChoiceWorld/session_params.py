# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-07-12 16:18:59
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
        self.LAST_TRIAL_DATA = adaptive.load_data(self.PREVIOUS_SESSION_PATH)
        self.LAST_SETTINGS_DATA = adaptive.load_settings(
            self.PREVIOUS_SESSION_PATH)
        # =====================================================================
        # ADAPTIVE STUFF
        # =====================================================================
        self.REWARD_AMOUNT = adaptive.init_reward_amount(self)
        self.CALIB_FUNC = adaptive.init_calib_func(self)
        self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range(self)
        self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)
        self.STIM_GAIN = adaptive.init_stim_gain(self)
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
        self = sound.init_sounds(self)
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

    def get_port_events(self, events, name=''):
        return iotasks.get_port_events(events, name=name)

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

    # =========================================================================
    # SOUND
    # =========================================================================
    def _init_sounds(self):
        if self.SOFT_SOUND:
            self.UPLOADER_TOOL = None
            self.GO_TONE = sound.make_sound(
                rate=self.SOUND_SAMPLE_FREQ,
                frequency=self.GO_TONE_FREQUENCY,
                duration=self.GO_TONE_DURATION,
                amplitude=self.GO_TONE_AMPLITUDE,
                fade=0.01,
                chans='L+TTL')
            self.WHITE_NOISE = sound.make_sound(
                rate=self.SOUND_SAMPLE_FREQ,
                frequency=-1,
                duration=self.WHITE_NOISE_DURATION,
                amplitude=self.WHITE_NOISE_AMPLITUDE,
                fade=0.01,
                chans='L+TTL')

            self.OUT_TONE = ('SoftCode', 1)
            self.OUT_NOISE = ('SoftCode', 2)
        else:
            msg = f"""
        ##########################################
        SOUND BOARD NOT IMPLEMTNED YET!!",
        PLEASE GO TO:
        iblrig_params/IBL/tasks/{self.PYBPOD_PROTOCOL}/task_settings.py
        and set
          SOFT_SOUND = 'sysdefault' or 'xonar'
        ##########################################"""
            log.error(msg)
            raise(NotImplementedError)

    def play_tone(self):
        self.SD.play(self.GO_TONE, self.SOUND_SAMPLE_FREQ)  # , mapping=[1, 2])

    def play_noise(self):
        self.SD.play(self.WHITE_NOISE, self.SOUND_SAMPLE_FREQ)

    def stop_sound(self):
        self.SD.stop()

    # =========================================================================
    # BONSAI WORKFLOWS
    # =========================================================================
    def start_visual_stim(self):
        if self.USE_VISUAL_STIMULUS and self.BONSAI:
            # Run Bonsai workflow
            here = os.getcwd()
            os.chdir(str(
                Path(self.VISUAL_STIM_FOLDER) / self.VISUAL_STIMULUS_TYPE))
            bns = self.BONSAI
            wkfl = self.VISUAL_STIMULUS_FILE

            evt = "-p:FileNameEvents=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_iblrig_encoderEvents.raw.ssv")
            pos = "-p:FileNamePositions=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_iblrig_encoderPositions.raw.ssv")
            itr = "-p:FileNameTrialInfo=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_iblrig_encoderTrialInfo.raw.ssv")
            mic = "-p:FileNameMic=" + os.path.join(
                self.SESSION_RAW_DATA_FOLDER,
                "_iblrig_micData.raw.wav")

            com = "-p:REPortName=" + self.COM['ROTARY_ENCODER']
            rec = "-p:RecordSound=" + str(self.RECORD_SOUND)

            sync_x = "-p:sync_x=" + str(self.SYNC_SQUARE_X)
            sync_y = "-p:sync_y=" + str(self.SYNC_SQUARE_Y)
            start = '--start'
            noeditor = '--noeditor'

            if self.BONSAI_EDITOR:
                subprocess.Popen(
                    [bns, wkfl, start, pos, evt, itr, com, mic, rec, sync_x, sync_y])
            elif not self.BONSAI_EDITOR:
                subprocess.Popen(
                    [bns, wkfl, noeditor, pos, evt, itr, com, mic, rec, sync_x, sync_y])
            time.sleep(5)
            os.chdir(here)
        else:
            self.USE_VISUAL_STIMULUS = False

    def start_camera_recording(self):
        if (self.RECORD_VIDEO is False
                and self.OPEN_CAMERA_VIEW is False):
            return
        # Run Workflow
        here = os.getcwd()
        os.chdir(self.VIDEO_RECORDING_FOLDER)

        bns = self.BONSAI
        wkfl = self.VIDEO_RECORDING_FILE

        ts = '-p:TimestampsFileName=' + os.path.join(
            self.SESSION_RAW_VIDEO_DATA_FOLDER,
            '_iblrig_leftCamera.timestamps.ssv')
        vid = '-p:VideoFileName=' + os.path.join(
            self.SESSION_RAW_VIDEO_DATA_FOLDER,
            '_iblrig_leftCamera.raw.avi')
        rec = '-p:SaveVideo=' + str(self.RECORD_VIDEO)

        start = '--start'

        subprocess.Popen([bns, wkfl, start, ts, vid, rec])
        time.sleep(1)
        os.chdir(here)

    # =========================================================================
    # LAST TRIAL DATA
    # =========================================================================
    def _load_last_trial(self, i=-1):
        if self.PREVIOUS_DATA_FILE is None:
            return
        trial_data = raw.load_data(self.PREVIOUS_SESSION_PATH)

        return trial_data[i] if trial_data else None

    def _load_last_settings_file(self):
        if not self.PREVIOUS_SETTINGS_FILE:
            return

        return raw.load_settings(self.PREVIOUS_SESSION_PATH)

    # =========================================================================
    # ADAPTIVE REWARD AND GAIN RULES
    # =========================================================================
    def _init_reward_amount(self):
        if not self.ADAPTIVE_REWARD:
            return self.REWARD_AMOUNT

        if self.LAST_TRIAL_DATA is None:
            return self.AR_INIT_VALUE
        elif self.LAST_TRIAL_DATA and self.LAST_TRIAL_DATA['trial_num'] < 200:
            out = self.LAST_TRIAL_DATA['reward_amount']
        elif self.LAST_TRIAL_DATA and self.LAST_TRIAL_DATA['trial_num'] >= 200:
            out = self.LAST_TRIAL_DATA['reward_amount'] - self.AR_STEP
            out = self.AR_MIN_VALUE if out <= self.AR_MIN_VALUE else out

        if 'SUBJECT_WEIGHT' not in self.LAST_SETTINGS_DATA.keys():
            return out

        previous_weight_factor = self.LAST_SETTINGS_DATA['SUBJECT_WEIGHT'] / 25
        previous_water = self.LAST_TRIAL_DATA['water_delivered'] / 1000

        if previous_water < previous_weight_factor:
            out = self.LAST_TRIAL_DATA['reward_amount'] + self.AR_STEP

        return out

    def _init_calib_func(self):
        if not self.AUTOMATIC_CALIBRATION:
            return

        if self.LATEST_WATER_CALIBRATION_FILE:
            # Load last calibration df1
            df1 = pd.read_csv(self.LATEST_WATER_CALIBRATION_FILE)
            # make interp func
            if df1.empty:
                msg = f"""
            ##########################################
                 Water calibration file is emtpy!
            ##########################################"""
                log.error(msg)
                raise(ValueError)
            time2vol = sp.interpolate.pchip(df1["open_time"],
                                            df1["weight_perdrop"])
            return time2vol
        else:
            return

    def _init_reward_valve_time(self):
        # Calc reward valve time
        if not self.AUTOMATIC_CALIBRATION:
            out = self.CALIBRATION_VALUE / 3 * self.REWARD_AMOUNT
        elif self.AUTOMATIC_CALIBRATION and self.CALIB_FUNC is not None:
            out = 0
            while np.round(self.CALIB_FUNC(out), 3) < self.REWARD_AMOUNT:
                out += 1
            out /= 1000
        elif self.AUTOMATIC_CALIBRATION and self.CALIB_FUNC is None:
            msg = """
            ##########################################
                  NO CALIBRATION FILE WAS FOUND:
            Calibrate the rig or use a manual calibration
            PLEASE GO TO:
            iblrig_params/IBL/tasks/{self.PYBPOD_PROTOCOL}/task_settings.py
            and set:
              AUTOMATIC_CALIBRATION = False
              CALIBRATION_VALUE = <MANUAL_CALIBRATION>
            ##########################################"""
            log.error(msg)
            raise(ValueError)

        if out >= 1:
            msg = """
            ##########################################
                REWARD VALVE TIME IS TOO HIGH!
            Probably because of a BAD calibration file
            Calibrate the rig or use a manual calibration
            PLEASE GO TO:
            iblrig_params/IBL/tasks/{self.PYBPOD_PROTOCOL}/task_settings.py
            and set:
              AUTOMATIC_CALIBRATION = False
              CALIBRATION_VALUE = <MANUAL_CALIBRATION>
            ##########################################"""
            log.error(msg)
            raise(ValueError)

        return float(out)

    def _init_stim_gain(self):
        if not self.ADAPTIVE_GAIN:
            return self.STIM_GAIN

        if self.LAST_TRIAL_DATA and self.LAST_TRIAL_DATA['trial_num'] >= 200:
            stim_gain = self.AG_MIN_VALUE
        else:
            stim_gain = self.AG_INIT_VALUE

        return stim_gain

    # =========================================================================
    # OSC CLIENT
    # =========================================================================
    def _init_osc_client(self):
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
            log.error("Multiple subjects found in PYBPOD_SUBJECTS")
            raise(IOError)

        self.PYBPOD_SUBJECT_EXTRA = [
          json.loads(x) for x in self.PYBPOD_SUBJECT_EXTRA[1:-1].split('","')]
        if len(self.PYBPOD_SUBJECT_EXTRA) == 1:
            self.PYBPOD_SUBJECT_EXTRA = self.PYBPOD_SUBJECT_EXTRA[0]

    # =========================================================================
    # SERIALIZE, COPY AND SAVE
    # =========================================================================
    def _save_session_settings(self):
        with open(self.SETTINGS_FILE_PATH, 'a') as f:
            f.write(json.dumps(self, cls=ComplexEncoder, indent=1))
            f.write('\n')
        return

    def _copy_task_code(self):
        # Copy behavioral task python code
        src = os.path.join(self.IBLRIG_PARAMS_FOLDER, 'IBL', 'tasks',
                           self.PYBPOD_PROTOCOL)
        dst = os.path.join(self.SESSION_RAW_DATA_FOLDER, self.PYBPOD_PROTOCOL)
        shutil.copytree(src, dst)
        # Copy stimulus folder with bonsai workflow
        src = str(Path(self.VISUAL_STIM_FOLDER) / self.VISUAL_STIMULUS_TYPE)
        dst = str(Path(self.SESSION_RAW_DATA_FOLDER) /
                  self.VISUAL_STIMULUS_TYPE)
        shutil.copytree(src, dst)
        # Copy video recording folder with bonsai workflow
        src = self.VIDEO_RECORDING_FOLDER
        dst = os.path.join(self.SESSION_RAW_VIDEO_DATA_FOLDER,
                           'camera_recordings')
        shutil.copytree(src, dst)

    def _save_task_code(self):
        # zip all existing folders
        # Should be the task code folder and if available stimulus code folder
        behavior_code_files = [
            os.path.join(self.SESSION_RAW_DATA_FOLDER, x)
            for x in os.listdir(self.SESSION_RAW_DATA_FOLDER)
            if os.path.isdir(os.path.join(self.SESSION_RAW_DATA_FOLDER, x))
        ]
        SessionParamHandler.zipit(
            behavior_code_files, os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                              '_iblrig_taskCodeFiles.raw.zip'))

        video_code_files = [
            os.path.join(self.SESSION_RAW_VIDEO_DATA_FOLDER, x)
            for x in os.listdir(self.SESSION_RAW_VIDEO_DATA_FOLDER)
            if os.path.isdir(os.path.join(
                self.SESSION_RAW_VIDEO_DATA_FOLDER, x))]
        SessionParamHandler.zipit(
            video_code_files, os.path.join(self.SESSION_RAW_VIDEO_DATA_FOLDER,
                                           '_iblrig_videoCodeFiles.raw.zip'))

        [shutil.rmtree(x) for x in behavior_code_files + video_code_files]

    def _configure_rotary_encoder(self, RotaryEncoderModule):
        m = RotaryEncoderModule(self.COM['ROTARY_ENCODER'])
        m.set_zero_position()  # Not necessarily needed
        m.set_thresholds(self.ROTARY_ENCODER.SET_THRESHOLDS)
        m.enable_thresholds(self.ROTARY_ENCODER.ENABLE_THRESHOLDS)
        m.close()

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
        r = "/home/nico/Projects/IBL/IBL-github/iblrig"
        _task_settings.IBLRIG_FOLDER = r
        d = ("/home/nico/Projects/IBL/IBL-github/iblrig/scratch/" +
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
