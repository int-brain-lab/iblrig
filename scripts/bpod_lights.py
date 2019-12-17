#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, February 18th 2019, 1:46:37 pm
import logging
import struct
import sys

import serial

import iblrig.params as params

log = logging.getLogger("iblrig")


def main(comport: str, command: int):
    if not comport:
        comport = params.get_board_comport()
    ser = serial.Serial(port=comport, baudrate=115200, timeout=1)
    ser.write(struct.pack("cB", b":", command))
    ser.close()
    log.debug(f"Sent <:{command}> to {comport}")
    return


if __name__ == "__main__":
    if len(sys.argv) == 2:
        comport = params.get_board_comport()
        command = sys.argv[1]
    else:
        comport = sys.argv[1]
        command = sys.argv[2]

    main(comport, int(command))
