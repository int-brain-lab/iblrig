import platform
from glob import glob
from pathlib import Path
import time
import usb.core

from serial import Serial
import serial.tools.list_ports

import logging
import numpy as np
# import pandas as pd

from iblutil.util import setup_logger
import iblrig.base_tasks
from pybpodapi.protocol import Bpod  # StateMachine

# set up logging
log = setup_logger('iblrig', level='DEBUG')


# function for querying a serial device
def query(s_obj, req, n=1):
    s_obj.write(req)
    return s.read(n)


issues = 0

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
    log.warning(f" ├ ✘  {p[0]} is undefined (OK if you don't want to use it)")
if not any(tmp):
    log.info(' ├ ✔  no undefined serial ports found')
ports = {k: v for k, v in ports.items() if v is not None}

# check for duplicate serial ports
seen = set()
for p in [x for x in ports.values() if x in seen or seen.add(x)]:
    log.critical(f' ├ ✘  Duplicate serial port: "{p}"')
    issues += 1
log.info(' ├ ✔  no duplicate serial ports found')

# collect valid ports
match platform.system():
    case 'Windows':
        valid_ports = [f'COM{i + 1}' for i in range(256)]
    case 'Linux':
        valid_ports = glob('/dev/tty[A-Za-z]*')
    case _:
        log.critical(f' ├ ✘  Unsupported platform: "{platform.system()}"')
        issues += 1

# check for invalid port-strings
for p in [(k, v) for k, v in ports.items() if v not in valid_ports]:
    log.critical(f'✘  Invalid serial port: "{p[1]}"')
    issues += 1
log.info(' └ ✔  no invalid port-strings found')

# check individual serial ports
port_info = [i for i in serial.tools.list_ports.comports()]
for (description, port) in ports.items():
    log.info(f'Checking serial port {description} ({port}):')

    # check if serial port exists
    try:
        info = [i for i in serial.tools.list_ports.comports() if i.device == port][0]
    except IndexError:
        log.critical(
            f' ├ ✘  "{port}" ({description}) cannot be found - is the device connected to the computer?')
        issues += 1
    log.info(' ├ ✔  serial port exists')

    # check if serial ports can be connected to
    try:
        s = Serial(port, timeout=1, writeTimeout=1)
    except serial.SerialException:
        log.critical(f' ├ ✘  Cannot connect to "{port}" ({description}) - is another process using the port?')
        issues += 1
    log.info(' ├ ✔  serial port can be connected to')

    # check correct assignments of serial ports
    match description:
        case "COM_BPOD":
            if query(s, b'6') == b'5':
                s.write(b'Z')
                log.info(' └ ✔  device seems to be a Bpod Finite State Machines')
            else:
                log.critical(
                    f' └ ✘  Device on port "{port}" does not appear to be a Bpod.')
                issues += 1
        case "COM_F2TTL":
            try:
                s.write(b'C')
            except serial.serialutil.SerialTimeoutException:
                port_info = serial.tools.list_ports.comports()
                port_info = next((p for p in port_info if p.name == s.name), None)

                # SAMD21 mini issue: not recognized by windows after reboot. Confirmed by Josh.
                log.critical(
                    f' └ ✘  Writing to port "{port}" timed out. Try to unplug and plug the device.')
                issues += 1
            if s.read() == (218).to_bytes(1, 'little'):
                log.info(' └ ✔  device seems to be a Frame2TTL')
            else:
                log.critical(
                    f' └ ✘  Device on port "{port}" does not appear to be a Frame2TTL.')
                issues += 1
        case "COM_ROTARY_ENCODER":
            if len(query(s, b'Q', 2)) > 1 and query(s, b'P00', 1) == (1).to_bytes(1, 'little'):
                log.info(' └ ✔  device seems to be a Rotary Encoder Module')
            else:
                log.critical(f' └ ✘  Device on port "{port}" does not appear to be a Rotary Encoder Module.')
                issues += 1
        case _:
            log.critical(' └ ✘  How did you get here??')
            issues += 1
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
        log.critical(' ├ ✘  Rotary Encoder Module is not connected to the Bpod')
        issues += 1
    if len(module) > 1:
        log.critical(' ├ ✘  More than one Rotary Encoder Module connected to the Bpod')
        issues += 1
    log.info(
        f' ├ ✔  module "{module[0].name}" is connected to the Bpod\'s module port #{module[0].serial_port}')

    s = serial.Serial(ports['COM_ROTARY_ENCODER'])
    s.write(b'I')
    time.sleep(.02)
    if s.in_waiting == 0:
        s.write(b'x')
    v = "1.x" if s.read(1) == (1).to_bytes(1, 'little') else "2+"
    log.info(f' ├ i  hardware version: {v}')
    log.info(f' ├ i  firmware version: {bpod.modules[0].firmware_version}')

    s.write(b'Z')
    p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
    log.warning(' ├ !  please move the wheel to the left (animal\'s POV) by a quarter turn')
    while np.abs(p) < 200:
        p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
    if p > 0:
        log.critical(' └ ✘  Rotary encoder seems to be wired incorrectly - try swapping A and B')
        issues += 1
    log.info(' └ ✔  rotary encoder is wired correctly')
    s.close()

if 'device_sound' in hw_settings and 'OUTPUT' in hw_settings['device_sound']:
    match hw_settings['device_sound']['OUTPUT']:
        case 'harp':
            log.info('Checking Harp Sound Card:')

            dev = usb.core.find(idVendor=0x04D8, idProduct=0xEE6A)
            if not dev:
                log.critical(' ├ ✘  Cannot find Harp Sound Card')
                issues += 1
            else:
                log.info(' ├ ✔  found USB device {:04X}:{:04X} (Harp Sound Card)'.format(dev.idVendor, dev.idProduct))

            dev = next((p for p in serial.tools.list_ports.comports() if (p.vid == 1027 and p.pid == 24577)), None)
            if not dev:
                log.critical(
                    ' ├ ✘  Cannot find Harp Sound Card\'s Serial port - did you plug in *both* USB ports of the device?')
                issues += 1
            else:
                log.info(' ├ ✔  found USB device {:04X}:{:04X} (FT232 UART), serial port: {}'.format(dev.vid, dev.pid,
                                                                                                     dev.name))

            module = [m for m in modules if m.name.startswith('SoundCard')]
            if len(module) == 0:
                log.critical(' └ ✘  Harp Sound Card is not connected to the Bpod')
                issues += 1
            elif len(module) > 1:
                log.critical(' └ ✘  More than one Harp Sound Card connected to the Bpod')
                issues += 1
            else:
                log.info(f' └ ✔  module "{module[0].name}" is connected to the Bpod\'s module port #{module[0].serial_port}')
        case _:
            pass

bpod.close()

# TO DO: bpod
# TO DO: BNC connections
# TO DO: camera
# TO DO: sound output
# TO DO: ambient module


if issues:
    logstr = f'   ✘  {issues} issues found' if issues > 1 else '   ✘  1 issue found'
    log.info('   ' + '═' * (len(logstr) - 3))
    log.critical(logstr)
else:
    log.info('   ══════════════════')
    log.info('   ✔  no issues found')
