#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, February 18th 2019, 1:46:37 pm
import json
import logging
import struct
import sys
from pathlib import Path

import serial

log = logging.getLogger('iblrig')

IBLRIG_FOLDER = Path(__file__).absolute().parent.parent
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / 'iblrig_params'


def get_com(key='BPOD'):
    fpath = IBLRIG_PARAMS_FOLDER / '.bpod_comports.json'
    with open(fpath, 'r') as f:
        comports = json.load(f)
    log.debug(f"Found {key} on port {comports[key]}")
    return comports[key]


def main(comport: str, command: int):
    if not comport:
        comport = get_com()
    ser = serial.Serial(port=comport, baudrate=115200, timeout=1)
    ser.write(struct.pack('cB', b':', command))
    ser.close()
    log.debug(f"Sent <:{command}> to {comport}")
    return


if __name__ == "__main__":
    if len(sys.argv) == 2:
        comport = get_com()
        command = sys.argv[1]
    else:
        comport = sys.argv[1]
        command = sys.argv[2]

    main(comport, int(command))
