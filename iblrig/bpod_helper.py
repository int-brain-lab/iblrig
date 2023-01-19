#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, December 9th 2019, 1:32:54 pm
# Rotary Encoder State Machine handler
import logging
import struct

import serial

import iblrig.params as params

log = logging.getLogger("iblrig")


def bpod_lights(comport: str, command: int):
    if not comport:
        comport = params.get_board_comport()
    ser = serial.Serial(port=comport, baudrate=115200, timeout=1)
    ser.write(struct.pack("cB", b":", command))
    # ser.read(1)
    ser.close()
    log.debug(f"Sent <:{command}> to {comport}")
    return
