"""
This module is intended to provide commonalities for all tasks.
Base classes for trial parameters and session parameters.
"""
from pathlib import Path
from abc import ABC
import datetime
import inspect
import logging
import yaml

import numpy as np
import scipy.interpolate

from pythonosc import udp_client

import iblrig.adaptive as adaptive
import iblrig.path_helper
from iblrig.path_helper import SessionPathCreator
from iblutil.util import Bunch
from iblrig.hardware import Bpod, MyRotaryEncoder, SoundDevice
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

    def __init__(self, debug=False, task_settings_file=None, hardware_settings_name='hardware_settings.yaml'):
        self.init_datetime = datetime.datetime.now()
        self.DEBUG = debug
        self.calibration = Bunch({})
        # Load pybpod settings
        self.pybpod_settings = iblrig.path_helper.load_pybpod_settings_yaml('pybpod_settings.yaml')
        # get another set of parameters from .iblrig_params.json
        self.hardware_settings = iblrig.path_helper.load_settings_yaml(hardware_settings_name)
        # Load the tasks settings
        task_settings_file = task_settings_file or Path(inspect.getfile(self.__class__)).parent.joinpath('task_parameters.yaml')
        if task_settings_file.exists():
            with open(task_settings_file) as fp:
                self.task_params = Bunch(yaml.safe_load(fp))
        else:
            self.task_params = None

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


class BpodMixin(object):

    def __init__(self, *args, **kwargs):
        self.bpod = Bpod()


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


class ValveMixin:
    def init_reward_amount(sph: object) -> float:
        if not sph.ADAPTIVE_REWARD:
            return sph.REWARD_AMOUNT

        if sph.LAST_TRIAL_DATA is None:
            return sph.AR_INIT_VALUE
        elif sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA["trial_num"] < 200:
            out = sph.LAST_TRIAL_DATA["reward_amount"]
        elif sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA["trial_num"] >= 200:
            out = sph.LAST_TRIAL_DATA["reward_amount"] - sph.AR_STEP
            out = sph.AR_MIN_VALUE if out <= sph.AR_MIN_VALUE else out

        if "SUBJECT_WEIGHT" not in sph.LAST_SETTINGS_DATA.keys():
            return out

        previous_weight_factor = sph.LAST_SETTINGS_DATA["SUBJECT_WEIGHT"] / 25
        previous_water = sph.LAST_TRIAL_DATA["water_delivered"] / 1000

        if previous_water < previous_weight_factor:
            out = sph.LAST_TRIAL_DATA["reward_amount"] + sph.AR_STEP

        out = sph.AR_MAX_VALUE if out > sph.AR_MAX_VALUE else out
        return out

    def __init__(self: object):
        self.valve = Bunch({})
        # the template settings files have a date in 2099, so assume that the rig is not calibrated if that is the case
        # the assertion on calibration is thrown when starting the device
        self.valve['is_calibrated'] = datetime.date.today() > self.hardware_settings['device_valve']['WATER_CALIBRATION_DATE']
        self.valve['fcn_vol2time'] = scipy.interpolate.pchip(
            self.hardware_settings['device_valve']["WATER_CALIBRATION_WEIGHT_PERDROP"],
            self.hardware_settings['device_valve']["WATER_CALIBRATION_OPEN_TIMES"],
        )
        if self.task_params.AUTOMATIC_CALIBRATION:
            self.valve['reward_time'] = self.valve['fcn_vol2time'](self.task_params.REWARD_AMOUNT) / 1e3
        else:  # this is the manual manual calibration value
            self.valve['reward_time'] = self.task_params.CALIBRATION_VALUE / 3 * self.task_params.REWARD_AMOUNT

    def start(self):
        # if the rig is not on manual settings, then the reward valve has to be calibrated to run the experiment
        assert self.task_params.AUTOMATIC_CALIBRATION is False or self.valve['is_calibrated'], """
            ##########################################
            NO CALIBRATION INFORMATION FOUND IN HARDWARE SETTINGS:
            Calibrate the rig or use a manual calibration
            PLEASE GO TO the task settings yaml file and set:
                'AUTOMATIC_CALIBRATION': false
                'CALIBRATION_VALUE' = <MANUAL_CALIBRATION>
            ##########################################"""
        # regardless of the calibration method, the reward valve time has to be lower than 1 second
        assert self.valve['reward_time'] < 1,\
            """
            ##########################################
                REWARD VALVE TIME IS TOO HIGH!
            Probably because of a BAD calibration file
            Calibrate the rig or use a manual calibration
            PLEASE GO TO the task settings yaml file and set:
                AUTOMATIC_CALIBRATION = False
                CALIBRATION_VALUE = <MANUAL_CALIBRATION>
            ##########################################"""


class SoundMixin:
    """
    Sound interface methods for state machine
    """
    def __init__(self):
        self.sound = Bunch({})
        self.sound['device'] = SoundDevice(output=self.task_params.SOFT_SOUND)
        # Create sounds and output actions of state machine
        self.sound['GO_TONE'] = iblrig.sound.make_sound(
            rate=self.sound.device.samplerate,
            frequency=self.task_params.GO_TONE_FREQUENCY,
            duration=self.task_params.GO_TONE_DURATION,
            amplitude=self.task_params.GO_TONE_AMPLITUDE,
            fade=0.01,
            chans=self.sound.device.channels)

        self.sound['WHITE_NOISE'] = iblrig.sound.make_sound(
            rate=self.sound.device.samplerate,
            frequency=-1,
            duration=self.task_params.WHITE_NOISE_DURATION,
            amplitude=self.task_params.WHITE_NOISE_AMPLITUDE,
            fade=0.01,
            chans=self.sound.device.channels)

        # SoundCard config params
        #
        if self.task_params.SOFT_SOUND is None:
            sound.configure_sound_card(
                sounds=[self.sound.GO_TONE, self.sound.WHITE_NOISE],
                indexes=[self.task_params.GO_TONE_IDX, self.task_params.WHITE_NOISE_IDX],
                sample_rate=self.sound.device.samplerate,
            )

        self.sound['OUT_TONE'] = ("SoftCode", 1) if self.task_params.SOFT_SOUND else ("Serial3", 6)
        self.sound['OUT_NOISE'] = ("SoftCode", 2) if self.task_params.SOFT_SOUND else ("Serial3", 7)
        self.sound['OUT_STOP_SOUND'] = ("SoftCode", 0) if self.task_params.SOFT_SOUND else ("Serial3", ord("X"))

    def play_tone(self):
        self.sound.device.play(self.sound.GO_TONE, self.sound.SOUND_SAMPLE_FREQ)

    def play_noise(self):
        self.sound.device.play(self.sound.WHITE_NOISE, self.sound.SOUND_SAMPLE_FREQ)

    def stop_sound(self):
        self.sound.device.stop()

    def send_sounds_to_harp(self):
        # self.card.send_sound(wave_int, GO_TONE_IDX, SampleRate._96000HZ, DataType.INT32)
        # self.card.send_sound(noise_int, WHITE_NOISE_IDX, SampleRate._96000HZ, DataType.INT32)
        pass


class ChoiceWorldSession(BaseSessionParamHandler,
                         RotaryEncoderMixin,
                         SoundMixin):  # BpodMixin, Frame2TTLMixin, CameraMixin

    def __init__(self, fmake=True, interactive=False, *args,  **kwargs):
        super(ChoiceWorldSession, self).__init__(*args, **kwargs)
        # BpodMixin.__init__(self, *args, **kwargs)
        RotaryEncoderMixin.__init__(self, *args, **kwargs)
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

    def time_elapsed(self):
        return datetime.datetime.now - self.init_datetime

    def softcode_handler(self, code):
        """
         Soft codes should work with resasonable latency considering our limiting
         factor is the refresh rate of the screen which should be 16.667ms @ a frame
         rate of 60Hz
         1 : go_tone
         2 : white_noise
         """
        if code == 0:
            self.stop_sound()
        elif code == 1:
            self.play_tone()
        elif code == 2:
            self.play_noise()
        elif code == 3:
            self.start_camera_recording()
