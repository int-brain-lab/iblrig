#!/usr/bin/env python
# @File: _iblrig_calibration_frame2TTL\session_params.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Thursday, June 6th 2019, 11:42:40 am
import logging

import iblrig.bonsai as bonsai

try:
    import user_settings
except ImportError:
    import iblrig.fake_user_settings as user_settings
import iblrig.iotasks as iotasks
from iblrig.path_helper import SessionPathCreator
from pythonosc import udp_client

log = logging.getLogger("iblrig")


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, make_folders=True):
        # =====================================================================
        # IMPORT task_settings, user_settings, and SessionPathCreator params
        # =====================================================================
        # ts = {
        #     i: task_settings.__dict__[i] for i in [x for x in dir(task_settings) if "__" not in x]
        # }
        # self.__dict__.update(ts)
        if "fake" in user_settings.__dict__["PYBPOD_CREATOR"]:
            msg = "No user settings found!\nUsing fake mouse!\n"
            log.warning(msg * 5)
        us = {
            i: user_settings.__dict__[i] for i in [x for x in dir(user_settings) if "__" not in x]
        }
        self.__dict__.update(us)
        self = iotasks.deserialize_pybpod_user_settings(self)
        spc = SessionPathCreator(
            self.PYBPOD_SUBJECTS[0], protocol=self.PYBPOD_PROTOCOL, make=make_folders
        )
        self.__dict__.update(spc.__dict__)
        # =====================================================================
        # OSC CLIENT
        # =====================================================================
        self.OSC_CLIENT_PORT = 7110
        self.OSC_CLIENT_IP = "127.0.0.1"
        self.OSC_CLIENT = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP, self.OSC_CLIENT_PORT)
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        iotasks.save_session_settings(self)
        iotasks.copy_task_code(self)
        iotasks.save_task_code(self)

    # =========================================================================
    # METHODS
    # =========================================================================
    def start_screen_color(self, display_idx):
        bonsai.start_screen_color(display_idx=display_idx)
        self.set_screen(rgb=[128, 128, 128])

    def stop_screen_color(self):
        self.OSC_CLIENT.send_message("/x", 1)

    def set_screen(self, rgb=[128, 128, 128]):
        ch = ["/r", "/g", "/b"]
        for color, i in zip(rgb, ch):
            self.OSC_CLIENT.send_message(i, color)

    # =========================================================================
    # JSON ENCODER PATCHES
    # =========================================================================
    def reprJSON(self):
        d = self.__dict__.copy()
        d["OSC_CLIENT"] = str(d["OSC_CLIENT"])
        return d


if __name__ == "__main__":
    print("Done!")
