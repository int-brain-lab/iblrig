# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
import logging
from sys import platform
import iblrig.adaptive as adaptive
import iblrig.iotasks as iotasks
from iblrig.base_tasks import ChoiceWorldSessionParamHandler
log = logging.getLogger("iblrig")


class SessionParamHandler(ChoiceWorldSessionParamHandler):
    """"Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""
    def __init__(self, debug=False, fmake=True, **kwargs):
        super(SessionParamHandler, self).__init__(debug=debug, fmake=fmake, **kwargs)
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
        # =====================================================================
        # ADAPTIVE STUFF
        # =====================================================================
        self.CALIB_FUNC = None
        if self.task.AUTOMATIC_CALIBRATION:
            self.CALIB_FUNC = adaptive.init_calib_func()
        self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range()
        self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        # if not self.DEBUG:
        #     iotasks.save_session_settings(self)
        #     iotasks.copy_task_code(self)
        #     iotasks.save_task_code(self)
        #     if "ephys" not in self.PYBPOD_BOARD:
        #         iotasks.copy_video_code(self)
        #         iotasks.save_video_code(self)
        #     self.bpod_lights(0)

