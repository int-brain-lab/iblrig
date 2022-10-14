#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
import logging
from sys import platform

import iblrig.iotasks as iotasks
from iblrig.path_helper import SessionPathCreator

log = logging.getLogger("iblrig")


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings, make=True):
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
        spc = SessionPathCreator(self.PYBPOD_SUBJECTS[0], protocol=self.PYBPOD_PROTOCOL, make=make)
        self.__dict__.update(spc.__dict__)
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        iotasks.save_session_settings(self)
        iotasks.copy_task_code(self)
        iotasks.save_task_code(self)

    # =========================================================================
    # METHODS
    # =========================================================================
    def reprJSON(self):
        def remove_from_dict(sx):
            if "weighings" in sx.keys():
                sx["weighings"] = None
            if "water_administration" in sx.keys():
                sx["water_administration"] = None
            return sx

        d = self.__dict__.copy()
        if isinstance(d["PYBPOD_SUBJECT_EXTRA"], list):
            sub = []
            for sx in d["PYBPOD_SUBJECT_EXTRA"]:
                sub.append(remove_from_dict(sx))
            d["PYBPOD_SUBJECT_EXTRA"] = sub
        elif isinstance(d["PYBPOD_SUBJECT_EXTRA"], dict):
            d["PYBPOD_SUBJECT_EXTRA"] = remove_from_dict(d["PYBPOD_SUBJECT_EXTRA"])
        return d


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
    import user_settings as _user_settings

    if platform == "linux":
        r = "/home/nico/Projects/IBL/github/iblrig"
        _task_settings.IBLRIG_FOLDER = r
        d = "/home/nico/Projects/IBL/github/iblrig_data"  # noqa
        _task_settings.IBLRIG_DATA_FOLDER = d

    sph = SessionParamHandler(_task_settings, _user_settings)
    # for k in sph.__dict__:
    #     print(f"{k}: {sph.__dict__[k]}")
    self = sph
    print("Done!")
