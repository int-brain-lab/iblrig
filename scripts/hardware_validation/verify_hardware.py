import platform
import time
from glob import glob
from pathlib import Path
from struct import unpack

import numpy as np
import serial.tools.list_ports
import usb.core
from serial import Serial

import iblrig.base_tasks

# import pandas as pd
from iblutil.util import setup_logger
from pybpodapi.protocol import Bpod, StateMachine

# set up logging
log = setup_logger('iblrig', level='DEBUG')

issues = 0


# function for querying a serial device
def query(s_obj, req, n=1, end: bool = False):
    s_obj.write(req)
    return s.read(n)


def log_fun(msg_type: str = 'info', msg: str = '', last: bool = False):
    global issues
    tree = '└' if last else '├'
    match msg_type:
        case 'head':
            pass
        case 'pass':
            level = 'info'
            symbol = '✔'
        case 'info':
            level = 'info'
            symbol = 'i'
        case 'warn':
            level = 'warning'
            symbol = '!'
        case 'fail':
            level = 'critical'
            symbol = '✘'
            issues += 1
        case _:
            level = 'critical'
            symbol = '?'

    if msg_type == 'head':
        log.info('\033[1m' + msg)
    else:
        getattr(log, level)(f' {tree} {symbol}  {msg}')


# read hardware_settings.yaml
log_fun('head', 'Checking hardware_settings.yaml:')
file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
hw_settings = iblrig.path_helper.load_settings_yaml(file_settings)

# collect all port-strings
ports = [d for d in hw_settings.values() if isinstance(d, dict)]
ports = {k: v for x in ports for k, v in x.items() if k[0:4].startswith('COM_')}

# check for undefined serial ports (warn only)
tmp = [(k, v) for k, v in ports.items() if v is None]
for p in tmp:
    log_fun('fail', f"{p[0]} is undefined (OK if you don't want to use it)")
if not any(tmp):
    log_fun('pass', 'no undefined serial ports found')
ports = {k: v for k, v in ports.items() if v is not None}

# check for duplicate serial ports
seen = set()
for p in [x for x in ports.values() if x in seen or seen.add(x)]:
    log_fun('fail', f'duplicate serial port: "{p}"')
else:
    log_fun('pass', 'no duplicate serial ports found')

# collect valid ports
match platform.system():
    case 'Windows':
        valid_ports = [f'COM{i + 1}' for i in range(256)]
    case 'Linux':
        valid_ports = glob('/dev/tty*')
    case _:
        raise Exception(f'Unsupported platform: "{platform.system()}"')

# check for invalid port-strings
for p in [(k, v) for k, v in ports.items() if v not in valid_ports]:
    log_fun('fail', f'invalid serial port: "{p[1]}"', last=True)
else:
    log_fun('pass', 'no invalid port-strings found', last=True)

# check individual serial ports
port_info = [i for i in serial.tools.list_ports.comports()]
for description, port in ports.items():
    log_fun('head', f'Checking serial port {description} ({port}):')

    # check if serial port exists
    try:
        info = [i for i in serial.tools.list_ports.comports() if i.device == port][0]
    except IndexError:
        log_fun('fail', f'{port} ({description}) cannot be found - is the device connected to the computer?', last=True)
        continue
    else:
        log_fun('pass', 'serial port exists')

    # check if serial ports can be connected to
    try:
        s = Serial(port, timeout=1, writeTimeout=1)
    except serial.SerialException:
        log_fun('fail', f'cannot connect to {port} ({description}) - is another process using the port?', last=True)
        continue
    else:
        log_fun('pass', 'serial port can be connected to')

    # check correct assignments of serial ports
    ok = False
    match description:
        case 'COM_BPOD':
            device_name = 'Bpod Finite State Machine'
            ok = query(s, b'6') == b'5'
            if ok:
                s.write(b'Z')
        case 'COM_F2TTL':
            device_name = 'Frame2TTL'
            try:
                s.write(b'C')
            except serial.serialutil.SerialTimeoutException:
                port_info = serial.tools.list_ports.comports()
                port_info = next((p for p in port_info if p.name == s.name), None)

                # SAMD21 mini issue: not recognized by windows after reboot. Confirmed by Josh.
                log_fun('fail', f'writing to port {port} timed out. Try to unplug and plug the device.', last=True)
                continue
            finally:
                ok = s.read() == (218).to_bytes(1, 'little')
        case 'COM_ROTARY_ENCODER':
            device_name = 'Rotary Encoder Module'
            ok = len(query(s, b'Q', 2)) > 1 and query(s, b'P00', 1) == (1).to_bytes(1, 'little')
        case _:
            raise Exception('How did you get here??')
    s.close()

    if ok:
        log_fun('pass', f'device on port {port} seems to be a {device_name}', last=True)
    else:
        log_fun('fail', f'device on port {port} does not appear to be a {device_name}', last=True)

    # To Do: Look into this required delay
    time.sleep(0.02)

# check bpod modules
bpod = Bpod(hw_settings['device_bpod']['COM_BPOD'])
modules = [m for m in bpod.bpod_modules.modules if m.connected]

if 'COM_ROTARY_ENCODER' in ports:
    log_fun('head', 'Checking Rotary Encoder Module:')
    module = [m for m in modules if m.name.startswith('RotaryEncoder')]
    if len(module) == 0:
        log_fun('fail', 'Rotary Encoder Module is not connected to the Bpod')
    elif len(module) > 1:
        log_fun('fail', 'more than one Rotary Encoder Module connected to the Bpod')
    else:
        log_fun('pass', f'module "{module[0].name}" is connected to the Bpod\'s module port #{module[0].serial_port}')

    s = serial.Serial(ports['COM_ROTARY_ENCODER'])
    s.write(b'I')
    time.sleep(0.02)
    if s.in_waiting == 0:
        s.write(b'x')
    v = '1.x' if s.read(1) == (1).to_bytes(1, 'little') else '2+'
    log_fun('info', f'hardware version: {v}')
    log_fun('info', f'firmware version: {bpod.modules[0].firmware_version}')

    s.write(b'Z')
    p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
    log_fun('warn', "please move the wheel to the left (animal's POV) by a quarter turn")
    while np.abs(p) < 200:
        p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
    if p > 0:
        log_fun('fail', 'Rotary encoder seems to be wired incorrectly - try swapping A and B', last=True)
    else:
        log_fun('pass', 'rotary encoder is wired correctly', last=True)
    s.close()

if 'device_sound' in hw_settings and 'OUTPUT' in hw_settings['device_sound']:
    match hw_settings['device_sound']['OUTPUT']:
        case 'harp':
            log_fun('head', 'Checking Harp Sound Card:')

            dev = usb.core.find(idVendor=0x04D8, idProduct=0xEE6A)
            if not dev:
                log_fun('fail', 'Cannot find Harp Sound Card')
            else:
                log_fun('pass', f'found USB device {dev.idVendor:04X}:{dev.idProduct:04X} (Harp Sound Card)')

            dev = next((p for p in serial.tools.list_ports.comports() if (p.vid == 1027 and p.pid == 24577)), None)
            if not dev:
                log_fun('fail', "cannot find Harp Sound Card's Serial port - did you plug in *both* USB ports of the device?")
            else:
                log_fun('pass', f'found USB device {dev.vid:04X}:{dev.pid:04X} (FT232 UART), serial port: {dev.name}')

            module = [m for m in modules if m.name.startswith('SoundCard')]
            if len(module) == 0:
                log_fun('fail', 'Harp Sound Card is not connected to the Bpod', last=True)
            elif len(module) > 1:
                log_fun('fail', 'more than one Harp Sound Card connected to the Bpod', last=True)
            else:
                log_fun(
                    'pass',
                    f'module "{module[0].name}" is connected to the Bpod\'s module port #{module[0].serial_port}',
                    last=True,
                )
        case _:
            pass

log_fun('head', 'Checking Ambient Module:')
module = next((m for m in modules if m.name.startswith('AmbientModule')), None)
if module:
    log_fun('pass', f'module "{module.name}" is connected to the Bpod\'s module port #{module.serial_port}')
    log_fun('info', f'firmware version: {module.firmware_version}')
    module.start_module_relay()
    bpod.bpod_modules.module_write(module, 'R')
    (t, p, h) = unpack('3f', bytes(bpod.bpod_modules.module_read(module, 12)))
    module.stop_module_relay()
    log_fun('info', f'temperature: {t:.1f} °C')
    log_fun('info', f'air pressure: {p / 100:.1f} mbar')
    log_fun('info', f'rel. humidity: {h:.1f}%')
else:
    log_fun('fail', 'Could not find Ambient Module', last=True)

if 'device_cameras' in hw_settings and isinstance(hw_settings['device_cameras'], dict):
    log_fun('head', 'Checking Camera Trigger:')
    sma = StateMachine(bpod)
    sma.add_state(
        state_name='collect',
        state_timer=1,
        state_change_conditions={'Tup': 'exit'},
    )
    bpod.send_state_machine(sma)
    bpod.run_state_machine(sma)
    triggers = [i.host_timestamp for i in bpod.session.current_trial.events_occurrences if i.content == 'Port1In']
    np.mean(np.diff(triggers))
    if len(triggers) == 0:
        log_fun('fail', 'could not read camera trigger', last=True)
    else:
        log_fun('pass', 'successfully read camera trigger')
        log_fun('info', f'average frame-rate: {np.mean(np.diff(triggers)) * 1E3:.3f} Hz', last=True)

bpod.close()

# TO DO: bpod
# TO DO: BNC connections
# TO DO: sound output


if issues:
    msg = f"   ✘  {issues} issue{'s' if issues > 1 else ''} found"
    log.info('   ' + '═' * (len(msg) - 3))
    log.critical(msg)
else:
    log.info('   ══════════════════')
    log.info('\033[1m   ✔  no issues found')
