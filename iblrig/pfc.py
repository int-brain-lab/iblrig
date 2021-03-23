#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, September 4th 2019, 4:24:59 pm
"""Pre flight checklist
Define task, user, subject and board
Check Alyx connection
    Alyx present:
       Load COM ports
       Load water calibration data and func
       Load frame2TTL thresholds
       Check Bpod, RE, and Frame2TTL
       Set frame2TTL thresholds
       Create folders
       Create session on Alyx
       Open session notes in browser
       Run task
    Alyx absent:

    Load COM ports
end with user input
"""
import datetime
import logging
import struct

import serial
from dateutil.relativedelta import relativedelta
from oneibl.one import ONE
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule

import iblrig.logging_  # noqa
import iblrig.params as params
from iblrig.frame2TTL import Frame2TTL

log = logging.getLogger("iblrig")
log.setLevel(logging.DEBUG)


def _grep_param_dict(pattern):
    pardict = params.load_params_file(silent=True)
    return {k: pardict[k] for k in pardict if pattern in k}


def params_comports_ok() -> bool:
    # Load PARAMS file ports
    # If file exists open file if not initialize
    subdict = _grep_param_dict("COM")
    out = True if all(subdict.values()) else False
    if not out:
        log.warning(f"Not all comports are present: {subdict}")
    log.debug("Loading params file...")
    return out


def calibration_dates_ok() -> bool:
    """
    """
    subdict = _grep_param_dict("DATE")
    thresh = {
        "F2TTL_CALIBRATION_DATE": datetime.timedelta(days=7),
        "SCREEN_FREQ_TEST_DATE": relativedelta(months=4),
        "SCREEN_LUX_DATE": relativedelta(months=4),
        "WATER_CALIBRATION_DATE": relativedelta(months=1),
        "BPOD_TTL_TEST_DATE": relativedelta(months=4),
    }
    assert thresh.keys() == subdict.keys()

    today = datetime.datetime.now().date()

    cal_dates_exist = True if all(subdict.values()) else False
    if not cal_dates_exist:
        log.warning(f"Not all calibration dates are present: {subdict}")
    else:
        subdict = {k: datetime.datetime.strptime(v, "%Y-%m-%d").date() for k, v in subdict.items()}
        out = dict.fromkeys(subdict)
        for k in subdict:
            out[k] = subdict[k] + thresh[k] < today
    if not all(out.values()):
        log.warning(f"Outdated calibrations: {[k for k, v in out.items() if not v]}")
    return all(out.values())

# Check if Alyx is accessible
log.debug("Alyx: Connecting...")
one = ONE()
# Check PARAMS values
checks = []
for k in PARAMS:
    if PARAMS[k] is None or PARAMS[k] == "":
        checks.append(1)
        log.warning(f"{k}: Value not found")
if sum(checks) != 0:
    log.error("Missing values in params file")
    raise (ValueError)

# Check board name
assert PARAMS["NAME"] == params.get_pybpod_board_name()
# COM ports check
assert PARAMS["COM_BPOD"] == params.get_pybpod_board_comport()
PARAMS["COM_ROTARY_ENCODER"]
PARAMS["COM_F2TTL"]
# F2TTL CALIBRATION: check f2ttl values from params, warn if old calibration
PARAMS["F2TTL_DARK_THRESH"]
PARAMS["F2TTL_LIGHT_THRESH"]
PARAMS["F2TTL_CALIBRATION_DATE"]
# WATER CALIBRATION: check water calibration values from params, warn if old calibration
log.debug("Checking water calibration...")
PARAMS["WATER_CALIBRATION_RANGE"]
PARAMS["WATER_CALIBRATION_OPEN_TIMES"]
PARAMS["WATER_CALIBRATION_WEIGHT_PERDROP"]
PARAMS["WATER_CALIBRATION_DATE"]
# F2TTL CALIBRATION: check f2ttl values from params, warn if old calibration
# WATER CALIBRATION: check water calibration values from params, warn if old calibration
# raise BaseException

# Check RE
log.debug("RE: Connect")
m = RotaryEncoderModule(PARAMS["COM_ROTARY_ENCODER"])
log.debug("RE: set 0 position")
m.set_zero_position()  # Not necessarily needed
log.debug("RE: Close")
m.close()
# Check Bpod
log.debug("Bpod Connect")
ser = serial.Serial(port=PARAMS["COM_BPOD"], baudrate=115200, timeout=1)
log.debug("Bpod lights OFF")
ser.write(struct.pack("cB", b":", 0))
log.debug("Bpod lights ON")
ser.write(struct.pack("cB", b":", 1))
log.debug("Bpod Close")
ser.close()
# Check Frame2TTL (by setting the thresholds)
f = Frame2TTL(PARAMS["COM_F2TTL"])
assert f.connected == True
f.read_value() > 5
f.set_thresholds(dark=PARAMS["F2TTL_DARK_THRESH"], light=PARAMS["F2TTL_LIGHT_THRESH"])
f.close()
# Check Mic connection?

# Check Xonar sound card existence if on ephys rig

# Check HarpSoundCard if on ephys rig

# Cameras check + setup
# iblrig.camera_config

# Check Task IO Run fast habituation task with fast delays?

# Ask user info

# Create missing session folders

# Create Alyx session reference? NO

# Open Alyx session notes in browser? NO

print(".")
