import platform
from glob import glob
from pathlib import Path
import time

from serial import Serial
import serial.tools.list_ports

import logging
import numpy as np
# import pandas as pd

import iblrig.base_tasks
from pybpodapi.protocol import Bpod  # StateMachine

# set up logging
logging.basicConfig(
    format="%(levelname)-8s %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


# function for querying a serial device
def query(s_obj, req, n=1):
    s_obj.write(req)
    return s.read(n)


# read hardware_settings.yaml
log.info('Checking hardware_settings.yaml:')
file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
hw_settings = iblrig.path_helper.load_settings_yaml(file_settings)

# collect all port-strings
ports = [d for d in hw_settings.values() if isinstance(d, dict)]
ports = {k: v for x in ports for k, v in x.items() if k[0:4].startswith('COM_')}

# check for undefined serial ports (warn only)
tmp = [(k, v) for k, v in ports.items() if v is None]
for p in tmp:
    log.warning("✗ {} is undefined (OK if you don't want to use it)".format(p[0]))
if not any(tmp):
    log.info('✓ no undefined serial ports found')
ports = {k: v for k, v in ports.items() if v is not None}

# check for duplicate serial ports
seen = set()
for p in [x for x in ports.values() if x in seen or seen.add(x)]:
    raise Exception('Duplicate serial port: "{}"'.format(p))
log.info('✓ no duplicate serial ports found')

# collect valid ports
match platform.system():
    case 'Windows':
        valid_ports = ['COM{:d}'.format(i + 1) for i in range(256)]
    case 'Linux':
        valid_ports = glob('/dev/tty[A-Za-z]*')
    case _:
        raise Exception('Unsupported platform: "{}"'.format(platform.system()))

# check for invalid port-strings
for p in [(k, v) for k, v in ports.items() if v not in valid_ports]:
    raise Exception('Invalid serial port: "{}"'.format(p[1]))
log.info('✓ no invalid port-strings found')

# check individual serial ports
port_info = [i for i in serial.tools.list_ports.comports()]
for (description, port) in ports.items():
    log.info('Checking serial port {} ({}):'.format(port, description))

    # check if serial port exists
    try:
        info = [i for i in serial.tools.list_ports.comports() if i.device == port][0]
    except IndexError:
        raise Exception(
            '"{}" ({}) cannot be found - is the device connected to the computer?'.format(port, description))
    log.info('✓ serial port exists')

    # check if serial ports can be connected to
    try:
        s = Serial(port, timeout=1, writeTimeout=1)
    except serial.SerialException:
        raise Exception('Cannot connect to "{}" ({}) - is another process using the port?'.format(port, description))
    log.info('✓ serial port can be connected to')

    # check correct assignments of serial ports
    match description:
        case "COM_BPOD":
            if query(s, b'6') == b'5':
                s.write(b'Z')
                log.info('✓ device seems to be a Bpod Finite State Machines')
            else:
                raise Exception(
                    'Device on port "{}" does not appear to be a Bpod.'.format(port))
        case "COM_F2TTL":
            try:
                s.write(b'C')
            except serial.serialutil.SerialTimeoutException:
                # SAMD21 mini issue: not recognized by windows after reboot. Confirmed by Josh.
                raise Exception(
                    'Writing to port "{}" timed out. Try to unplug and plug the device.'.format(port))
            if s.read() == (218).to_bytes(1, 'little'):
                log.info('✓ device seems to be a Frame2TTL')
            else:
                raise Exception(
                    'Device on port "{}" does not appear to be a Frame2TTL.'.format(port))
        case "COM_ROTARY_ENCODER":
            if len(query(s, b'Q', 2)) > 1 and query(s, b'P00', 1) == (1).to_bytes(1, 'little'):
                log.info('✓ device seems to be a Rotary Encoder Module')
            else:
                raise Exception('Device on port "{}" does not appear to be a Rotary Encoder Module.'.format(port))
        case _:
            raise Exception('How did you get here??')
    s.close()

    # To Do: Look into this required delay
    time.sleep(.02)

# check bpod modules
bpod = Bpod(hw_settings['device_bpod']['COM_BPOD'])
modules = [m for m in bpod.bpod_modules.modules if m.connected]

if 'COM_ROTARY_ENCODER' in ports.keys():
    log.info('Checking Rotary Encoder Module:')
    module = [m for m in modules if m.name.startswith('RotaryEncoder')]
    if len(module) == 0:
        raise Exception('Rotary Encoder Module is not connected to the Bpod')
    if len(module) > 1:
        raise Exception('More than one Rotary Encoder Module connected to the Bpod')
    log.info('✓ module "{}" is connected to the Bpod\'s module port #{}'.format(module[0].name, module[0].serial_port))

    s = serial.Serial(ports['COM_ROTARY_ENCODER'])
    s.write(b'I')
    time.sleep(.02)
    if s.in_waiting == 0:
        s.write(b'x')
    v = "1.x" if s.read(1) == (1).to_bytes(1, 'little') else "2+"
    log.info('· hardware version: {}'.format(v))
    log.info('· firmware version: {}'.format(bpod.modules[0].firmware_version))

    s.write(b'Z')
    p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
    log.info('! please move the wheel to the left (animal\'s POV) by a quarter turn')
    while np.abs(p) < 200:
        p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
    if p > 0:
        raise Exception('Rotary encoder seems to be wired incorrectly - try swapping A and B')
    log.info('✓ rotary encoder is wired correctly')
    s.close()
bpod.close()

# TO DO: bpod
# TO DO: BNC connections
# TO DO: camera
# TO DO: sound output (harp can be matched through vendor/device ID?)
# TO DO: ambient module

log.info('---------------')
log.info('No issues found')
