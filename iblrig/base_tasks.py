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

import iblrig.path_helper
from iblutil.util import Bunch
from iblrig.hardware import Bpod, MyRotaryEncoder, SoundDevice
import iblrig.bonsai as bonsai
import iblrig.frame2TTL as frame2TTL

import iblrig.misc as misc
import iblrig.sound as sound

log = logging.getLogger("iblrig")

OSC_CLIENT_IP = "127.0.0.1"
OSC_CLIENT_PORT = 7110


class BaseSessionParamHandler(ABC):

    def __init__(self, debug=False, task_settings_file=None, hardware_settings_name='hardware_settings.yaml'):
        self.init_datetime = datetime.datetime.now()
        self.DEBUG = debug
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
        self.bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'])

    def check_bpod(self):
        assert self.bpod.modules is not None


class Frame2TTLMixin:
    """
    Frame 2 TTL interface for state machine
    """
    def __init__(self, *args, **kwargs):
        self.frame2ttl = None

    def start_frame2ttl(self):
        self.frame2ttl = frame2TTL.Frame2TTL(self.hardware_settings['device_frame2ttl']['COM_F2TTL'])
        self.frame2ttl.set_thresholds(
            dark=self.hardware_settings['device_frame2ttl']["F2TTL_DARK_THRESH"],
            light=self.hardware_settings['device_frame2ttl']["F2TTL_DARK_THRESH"])
        log.info("Frame2TTL: Thresholds set.")
        assert self.frame2ttl.connected


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

    def start_rotary_encoder(self):
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
    def get_reward_amount(self: object) -> float:
        # simply returns the reward amount if no adaptive rewared is used
        if not self.task_params.ADAPTIVE_REWARD:
            return self.task_params.REWARD_AMOUNT
        # simply returns the reward amount if no adaptive rewared is used
        if not self.task_params.ADAPTIVE_REWARD:
            return self.task_params.REWARD_AMOUNT
        else:
            raise NotImplementedError
        # first session : AR_INIT_VALUE, return
        # if total_water_session < (subject_weight / 25):
        #   minimum(last_reward + AR_STEP, AR_MAX_VALUE)  3 microliters AR_MAX_VALUE
        # last ntrials strictly below 200:
        #   keep the same reward
        # trial between 200 and above:
        #   maximum(last_reward - AR_STEP, AR_MIN_VALUE)  1.5 microliters AR_MIN_VALUE

        # when implementing this make sure the test is solid

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
