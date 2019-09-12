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
import iblrig.logging_
log = logging.getLogger('iblrig')

## Check if Alyx is accessible
import iblrig.alyx as alyx
log.debug("Alyx: Connecting")
one = alyx.get_one()
## Load COM ports
import json
from iblrig.path_helper import get_iblrig_folder
from pathlib import Path
IBLRIG_PATH = Path(get_iblrig_folder())
IBLRIG_PARAMS_PATH = IBLRIG_PATH.parent / 'iblrig_params'
assert(IBLRIG_PARAMS_PATH.exists())
BPOD_COMPORTS_FILE_PATH = IBLRIG_PARAMS_PATH / '.bpod_comports.json'
if BPOD_COMPORTS_FILE_PATH.exists():
    # If file exists open file
    with open(BPOD_COMPORTS_FILE_PATH, 'r') as f:
        COM = json.load(f)
else:
    # If file does not exist initialize:

## Load water calibration (date?)


## Load frame2TTL calibrated thresholds (date?)



## Check RE
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
log.debug("RE: Connect")
m = RotaryEncoderModule(COM['ROTARY_ENCODER'])
log.debug("RE: set 0 position")
m.set_zero_position()  # Not necessarily needed
log.debug("RE: Close")
m.close()
## Check Bpod
import serial
import struct
log.debug("Bpod Connect")
ser = serial.Serial(port=COM['BPOD'], baudrate=115200, timeout=1)
log.debug("Bpod lights OFF")
ser.write(struct.pack('cB', b':', 0))
log.debug("Bpod lights ON")
ser.write(struct.pack('cB', b':', 1))
log.debug("Bpod Close")
ser.close()
## Check Frame2TTL (by setting the thresholds)
from iblrig.frame2TTL import Frame2TTL
f = Frame2TTL(COM['FRAME2TTL'])
## Create missing session folders

## Run fast task to check IO

## Create Alyx session reference

## Open Alyx session notes in browser
print('.')
