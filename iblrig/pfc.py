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
import logging
import struct

import serial
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule

from oneibl.one import ONE
import iblrig.logging_  # noqa
import iblrig.params as params
from iblrig.frame2TTL import Frame2TTL

log = logging.getLogger("iblrig")
log.setLevel(logging.DEBUG)

# Check if Alyx is accessible
log.debug("Alyx: Connecting...")
one = ONE()
# Load PARAMS file ports
# If file exists open file if not initialize
log.debug("Loading params file...")
PARAMS = params.load_params_file()
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
assert PARAMS["NAME"] == params.get_board_name()
# COM ports check
PARAMS["COM_BPOD"]
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
f = Frame2TTL(PARAMS["COM_FRAME2TTL"])
# Create missing session folders

# Cameras check + setup
# iblrig.camera_config

# Run fast task to check IO

# Create Alyx session reference?

# Open Alyx session notes in browser?

# Ask user info
print(".")
