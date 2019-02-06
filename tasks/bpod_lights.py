import json
import logging
import struct
import sys
from pathlib import Path

import serial

log = logging.getLogger('iblrig')


def get_com(key='BPOD'):
    fpath = Path(__file__).parent / '.bpod_comports.json'
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
