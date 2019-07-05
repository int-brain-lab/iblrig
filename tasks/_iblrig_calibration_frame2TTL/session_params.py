#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, June 6th 2019, 11:42:40 am
import sys
from pathlib import Path
import logging

from pythonosc import udp_client

sys.path.append(str(Path(__file__).parent.parent))  # noqa
sys.path.append(str(Path(__file__).parent.parent.parent.parent))  # noqa
import iotasks
import alyx
from devices.F2TTL.F2TTL import frame2TTL
from path_helper import SessionPathCreator
log = logging.getLogger('iblrig')


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings):
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
                                 board=self.PYBPOD_BOARD, make=True)
        self.__dict__.update(spc.__dict__)
        self.alyx = alyx
        self.f2ttl = frame2TTL(self.COM['FRAME2TTL'])
        # =====================================================================
        # OSC CLIENT
        # =====================================================================
        self.OSC_CLIENT_PORT = 7110
        self.OSC_CLIENT_IP = '127.0.0.1'
        self.OSC_CLIENT = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP,
                                                     self.OSC_CLIENT_PORT)
        # # =====================================================================
        # # PREVIOUS DATA FILES
        # # =====================================================================
        # self.LAST_TRIAL_DATA = iotasks.load_data(self.PREVIOUS_SESSION_PATH)
        # self.LAST_SETTINGS_DATA = iotasks.load_settings(
        #     self.PREVIOUS_SESSION_PATH)
        # # =====================================================================
        # # ADAPTIVE STUFF
        # # =====================================================================
        # self.CALIB_FUNC = adaptive.init_calib_func(self)
        # self.CALIB_FUNC_RANGE = adaptive.init_calib_func_range(self)
        # self.REWARD_VALVE_TIME = adaptive.init_reward_valve_time(self)

        # # =====================================================================
        # # RUN VISUAL STIM
        # # =====================================================================
        self.VISUAL_STIMULUS_TYPE = 'screen_calibration'
        # bonsai.start_visual_stim(self)
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        iotasks.save_session_settings(self)
        iotasks.copy_task_code(self)
        iotasks.save_task_code(self)
        self.display_logs()

    # =========================================================================
    # METHODS
    # =========================================================================

    # =========================================================================
    # JSON ENCODER PATCHES
    # =========================================================================
    def reprJSON(self):
        d = self.__dict__.copy()
        d['OSC_CLIENT'] = str(d['OSC_CLIENT'])
        return d

    def display_logs(self):
        if self.PREVIOUS_DATA_FILE:
            msg = f"""
##########################################
PREVIOUS SESSION FOUND
LOADING PARAMETERS FROM: {self.PREVIOUS_DATA_FILE}
##########################################"""
            log.info(msg)


if __name__ == '__main__':
    print("Done!")
