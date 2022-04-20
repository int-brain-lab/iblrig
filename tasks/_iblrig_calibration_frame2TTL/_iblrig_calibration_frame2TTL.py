#!/usr/bin/env python
# @File: _iblrig_calibration_frame2TTL/_iblrig_calibration_frame2TTL.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Friday, November 5th 2021, 12:47:34 pm
import datetime
import logging
import time

import iblrig.params as params
from iblrig.frame2TTL import Frame2TTL
from session_params import SessionParamHandler

log = logging.getLogger("iblrig")

sph = SessionParamHandler()
f2ttl = Frame2TTL(sph.PARAMS["COM_F2TTL"])
white = [175, 175, 175] if f2ttl.hw_version == 2 else [255, 255, 255]

sph.start_screen_color(display_idx=sph.PARAMS["DISPLAY_IDX"])
time.sleep(3)
sph.set_screen(rgb=white)
time.sleep(1)
f2ttl.measure_white()
# f2ttl.measure_white(mode='manual')
sph.set_screen(rgb=[0, 0, 0])
time.sleep(1)
f2ttl.measure_black()
# f2ttl.measure_black(mode='manual')
resp = f2ttl.calc_recomend_thresholds()
if resp != -1:
    f2ttl.set_recommendations()

    patch = {
        "COM_F2TTL": f2ttl.serial_port,
        "F2TTL_HW_VERSION": f2ttl.hw_version,
        "F2TTL_DARK_THRESH": f2ttl.recomend_dark,
        "F2TTL_LIGHT_THRESH": f2ttl.recomend_light,
        "F2TTL_CALIBRATION_DATE": datetime.datetime.now().date().isoformat(),
    }

    params.update_params_file(data=patch)

sph.stop_screen_color()

print("Done")
