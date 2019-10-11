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
import json
import logging
import struct
from pathlib import Path

import serial
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule

import iblrig.alyx as alyx
import iblrig.logging_  # noqa
from iblrig.frame2TTL import Frame2TTL
from iblrig.path_helper import get_iblrig_folder

log = logging.getLogger('iblrig')
log.setLevel(logging.DEBUG)


# Check if Alyx is accessible
log.debug("Alyx: Connecting")
one = alyx.get_one()
# Load COM ports
IBLRIG_PATH = Path(get_iblrig_folder())
IBLRIG_PARAMS_PATH = IBLRIG_PATH.parent / 'iblrig_params'
assert(IBLRIG_PARAMS_PATH.exists())
PARAMS_FILE_PATH = IBLRIG_PARAMS_PATH / '.iblrig_params.json'
# TODO: use params module
if PARAMS_FILE_PATH.exists():
    # If file exists open file
    with open(PARAMS_FILE_PATH, 'r') as f:
        PARAMS = json.load(f)
else:
    # If file does not exist initialize:
    pass

# WATER CALIBRATION: check water calibration values from params, warn if old calibration

# F2TTL CALIBRATION: check f2ttl values from params, warn if old calibration

# Check RE
log.debug("RE: Connect")
m = RotaryEncoderModule(PARAMS['COM_ROTARY_ENCODER'])
log.debug("RE: set 0 position")
m.set_zero_position()  # Not necessarily needed
log.debug("RE: Close")
m.close()
# Check Bpod
log.debug("Bpod Connect")
ser = serial.Serial(port=PARAMS['COM_BPOD'], baudrate=115200, timeout=1)
log.debug("Bpod lights OFF")
ser.write(struct.pack('cB', b':', 0))
log.debug("Bpod lights ON")
ser.write(struct.pack('cB', b':', 1))
log.debug("Bpod Close")
ser.close()
# Check Frame2TTL (by setting the thresholds)
f = Frame2TTL(PARAMS['COM_FRAME2TTL'])
# Create missing session folders

# Run fast task to check IO

# Create Alyx session reference?

# Open Alyx session notes in browser?
print('.')
