"""
This modules extends the base_tasks modules by providing task logic around the Choice World protocol
"""
import datetime
import logging

import numpy as np

from iblutil.util import Bunch

from base_tasks import (BaseSessionParamHandler, RotaryEncoderMixin, SoundMixin, BpodMixin,
                        ValveMixin, Frame2TTLMixin, OSCClient)
from iblrig.path_helper import SessionPathCreator
import iblrig.iotasks as iotasks
import iblrig.user_input as user

log = logging.getLogger(__name__)


class ChoiceWorldSession(BaseSessionParamHandler,
                         RotaryEncoderMixin,
                         SoundMixin,
                         BpodMixin,
                         ValveMixin,
                         Frame2TTLMixin):  # , Frame2TTLMixin, CameraMixin

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
