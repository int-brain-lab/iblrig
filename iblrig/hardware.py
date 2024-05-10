"""
This modules contains hardware classes used to interact with modules.
"""

import logging
import os
import re
import shutil
import struct
import subprocess
import threading
import time
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
import serial
import sounddevice as sd
from annotated_types import Ge, Le
from pydantic import validate_call
from serial.tools import list_ports

from iblrig.tools import static_vars
from iblutil.util import Bunch
from pybpod_rotaryencoder_module.module import RotaryEncoder
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
from pybpodapi.bpod.bpod_io import BpodIO
from pybpodapi.bpod_modules.bpod_module import BpodModule
from pybpodapi.state_machine import StateMachine

SOFTCODE = IntEnum('SOFTCODE', ['STOP_SOUND', 'PLAY_TONE', 'PLAY_NOISE', 'TRIGGER_CAMERA'])

# some annotated types
Uint8 = Annotated[int, Ge(0), Le(255)]
ActionIdx = Annotated[int, Ge(1), Le(255)]

log = logging.getLogger(__name__)


class Bpod(BpodIO):
    can_control_led = True
    softcodes: dict[int, Callable] | None = None
    _instances = {}
    _lock = threading.Lock()
    _is_initialized = False

    def __new__(cls, *args, **kwargs):
        serial_port = args[0] if len(args) > 0 else ''
        serial_port = kwargs.get('serial_port', serial_port)
        with cls._lock:
            instance = Bpod._instances.get(serial_port, None)
            if instance:
                return instance
            instance = super().__new__(cls)
            Bpod._instances[serial_port] = instance
            return instance

    def __init__(self, *args, skip_initialization: bool = False, **kwargs):
        # skip initialization if it has already been performed before
        # IMPORTANT: only use this for non-critical tasks (e.g., flushing valve from GUI)
        if skip_initialization and self._is_initialized:
            return

        # try to instantiate once for nothing
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            log.warning("Couldn't instantiate BPOD, retrying once...")
            time.sleep(1)
            try:
                super().__init__(*args, **kwargs)
            except (serial.serialutil.SerialException, UnicodeDecodeError) as e:
                log.error(e)
                raise serial.serialutil.SerialException(
                    'The communication with Bpod is established but the Bpod is not responsive. '
                    'This is usually indicated by the device with a green light. '
                    'Please unplug the Bpod USB cable from the computer and plug it back in to start the task. '
                ) from e
        self.serial_messages = {}
        self.actions = Bunch({})
        self.can_control_led = self.set_status_led(True)
        self._is_initialized = True

    def close(self) -> None:
        super().close()
        self._is_initialized = False

    def __del__(self):
        with self._lock:
            if self.serial_port in Bpod._instances:
                Bpod._instances.pop(self.serial_port)

    @property
    def is_connected(self):
        return self.modules is not None

    @property
    def rotary_encoder(self):
        return self.get_module('rotary_encoder')

    @property
    def sound_card(self):
        return self.get_module('sound_card')

    @property
    def ambient_module(self):
        return self.get_module('^AmbientModule')

    def get_module(self, module_name: str) -> BpodModule | None:
        """Get module by name

        Parameters
        ----------
        module_name : str
            Regular Expression for matching a module name

        Returns
        -------
        BpodModule | None
            First matching module or None
        """
        if self.modules is None:
            return None
        if module_name in ['re', 'rotary_encoder']:
            module_name = r'^RotaryEncoder'
        elif module_name in ['sc', 'sound_card']:
            module_name = r'^SoundCard'
        modules = [x for x in self.modules if re.match(module_name, x.name)]
        if len(modules) > 1:
            log.critical(f'Found several Bpod modules matching `{module_name}`. Using first match: `{modules[0].name}`')
        if len(modules) > 0:
            return modules[0]

    @validate_call(config={'arbitrary_types_allowed': True})
    def _define_message(self, module: BpodModule | int, message: list[Uint8]) -> ActionIdx:
        """Define a serial message to be sent to a Bpod module as an output action within a state

        Parameters
        ----------
        module : BpodModule | int
            The targeted module, defined as a BpodModule instance or the module's port index
        message : list[int]
            The message to be sent - a list of up to three 8-bit integers

        Returns
        -------
        int
            The index of the serial message (1-255)

        Raises
        ------
        TypeError
            If module is not an instance of BpodModule or int

        Examples
        --------
        >>> id_msg_bonsai_show_stim = self._define_message(self.rotary_encoder, [ord("#"), 2])
        will then be used as such in StateMachine:
        >>> output_actions=[("Serial1", id_msg_bonsai_show_stim)]
        """
        if isinstance(module, BpodModule):
            module = module.serial_port
        message_id = len(self.serial_messages) + 1
        self.load_serial_message(module, message_id, message)
        self.serial_messages.update({message_id: {'target_module': module, 'message': message}})
        return message_id

    @validate_call(config={'arbitrary_types_allowed': True})
    def define_xonar_sounds_actions(self):
        self.actions.update(
            {
                'play_tone': ('SoftCode', SOFTCODE.PLAY_TONE),
                'play_noise': ('SoftCode', SOFTCODE.PLAY_NOISE),
                'stop_sound': ('SoftCode', SOFTCODE.STOP_SOUND),
            }
        )

    def define_harp_sounds_actions(self, module: BpodModule, go_tone_index: int = 2, noise_index: int = 3) -> None:
        module_port = f"Serial{module.serial_port if module is not None else ''}"
        self.actions.update(
            {
                'play_tone': (module_port, self._define_message(module, [ord('P'), go_tone_index])),
                'play_noise': (module_port, self._define_message(module, [ord('P'), noise_index])),
                'stop_sound': (module_port, ord('X')),
            }
        )

    def define_rotary_encoder_actions(self, module: BpodModule | None = None) -> None:
        if module is None:
            module = self.rotary_encoder
        module_port = f"Serial{module.serial_port if module is not None else ''}"
        self.actions.update(
            {
                'rotary_encoder_reset': (
                    module_port,
                    self._define_message(module, [RotaryEncoder.COM_SETZEROPOS, RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS]),
                ),
                'bonsai_hide_stim': (module_port, self._define_message(module, [ord('#'), 1])),
                'bonsai_show_stim': (module_port, self._define_message(module, [ord('#'), 8])),
                'bonsai_closed_loop': (module_port, self._define_message(module, [ord('#'), 3])),
                'bonsai_freeze_stim': (module_port, self._define_message(module, [ord('#'), 4])),
                'bonsai_show_center': (module_port, self._define_message(module, [ord('#'), 5])),
            }
        )

    def get_ambient_sensor_reading(self):
        if self.ambient_module is None:
            return {
                'Temperature_C': np.NaN,
                'AirPressure_mb': np.NaN,
                'RelativeHumidity': np.NaN,
            }
        self.ambient_module.start_module_relay()
        self.bpod_modules.module_write(self.ambient_module, 'R')
        reply = self.bpod_modules.module_read(self.ambient_module, 12)
        self.ambient_module.stop_module_relay()

        return {
            'Temperature_C': np.frombuffer(bytes(reply[:4]), np.float32)[0],
            'AirPressure_mb': np.frombuffer(bytes(reply[4:8]), np.float32)[0] / 100,
            'RelativeHumidity': np.frombuffer(bytes(reply[8:]), np.float32)[0],
        }

    def flush(self):
        """
        Flushes valve 1
        :return:
        """
        self.toggle_valve()

    def toggle_valve(self, duration=None):
        """
        Flushes valve 1 for duration (seconds)
        :return:
        """
        if duration is None:
            self.open_valve(open=True, valve_number=1)
            input('Press ENTER when done.')
            self.open_valve(open=False, valve_number=1)
        else:
            self.pulse_valve(open_time_s=duration)

    def open_valve(self, open: bool, valve_number: int = 1):
        self.manual_override(self.ChannelTypes.OUTPUT, self.ChannelNames.VALVE, valve_number, open)

    def pulse_valve(self, open_time_s: float, valve: str = 'Valve1'):
        sma = StateMachine(self)
        sma.add_state(
            state_name='flush', state_timer=open_time_s, state_change_conditions={'Tup': 'exit'}, output_actions=[(valve, 255)]
        )
        self.send_state_machine(sma)
        self.run_state_machine(sma)

    def pulse_valve_repeatedly(
        self, repetitions: int, open_time_s: float, close_time_s: float = 0.2, valve: str = 'Valve1'
    ) -> int:
        counter = 0

        def softcode_handler(_):
            nonlocal counter
            counter += 1

        original_softcode_handler = self.softcode_handler_function
        self.softcode_handler_function = softcode_handler

        sma = StateMachine(self)
        sma.set_global_timer(timer_id=1, timer_duration=(open_time_s + close_time_s) * repetitions)
        sma.add_state(state_name='start_timer', state_change_conditions={'Tup': 'open'}, output_actions=[('GlobalTimerTrig', 1)])
        sma.add_state(
            state_name='open',
            state_timer=open_time_s,
            state_change_conditions={'Tup': 'close'},
            output_actions=[(valve, 255), ('SoftCode', 1)],
        )
        sma.add_state(
            state_name='close', state_timer=close_time_s, state_change_conditions={'Tup': 'open', 'GlobalTimer1_End': 'exit'}
        )
        self.send_state_machine(sma)
        self.run_state_machine(sma)
        self.softcode_handler_function = original_softcode_handler
        return counter

    @static_vars(supported=True)
    def set_status_led(self, state: bool) -> bool:
        if self.can_control_led and self._arcom is not None:
            try:
                log.debug(f'{"en" if state else "dis"}abling Bpod Status LED')
                command = struct.pack('cB', b':', state)
                self._arcom.serial_object.write(command)
                if self._arcom.read_uint8() == 1:
                    return True
            except serial.SerialException:
                pass
            self._arcom.serial_object.reset_input_buffer()
            self._arcom.serial_object.reset_output_buffer()
            log.warning('Bpod device does not support control of the status LED. Please update firmware.')
        return False

    def valve(self, valve_id: int, state: bool):
        self.manual_override(self.ChannelTypes.OUTPUT, self.ChannelNames.VALVE, valve_id, state)

    @validate_call
    def register_softcodes(self, softcode_dict: dict[int, Callable]) -> None:
        """
        Register softcodes to be used in the state machine

        Parameters
        ----------
        softcode_dict : dict[int, Callable]
            dictionary of int keys with callables as values
        """
        self.softcodes = softcode_dict
        self.softcode_handler_function = lambda code: softcode_dict[code]()


class MyRotaryEncoder:
    def __init__(self, all_thresholds, gain, com, connect=False):
        self.RE_PORT = com
        self.WHEEL_PERIM = 31 * 2 * np.pi  # = 194,778744523
        self.deg_mm = 360 / self.WHEEL_PERIM
        self.mm_deg = self.WHEEL_PERIM / 360
        self.factor = 1 / (self.mm_deg * gain)
        self.SET_THRESHOLDS = [x * self.factor for x in all_thresholds]
        self.ENABLE_THRESHOLDS = [(x != 0) for x in self.SET_THRESHOLDS]
        # ENABLE_THRESHOLDS needs 8 bools even if only 2 thresholds are set
        while len(self.ENABLE_THRESHOLDS) < 8:
            self.ENABLE_THRESHOLDS.append(False)

        # Names of the RE events generated by Bpod
        self.ENCODER_EVENTS = [f'RotaryEncoder1_{x}' for x in list(range(1, len(all_thresholds) + 1))]
        # Dict mapping threshold crossings with name ov RE event
        self.THRESHOLD_EVENTS = dict(zip(all_thresholds, self.ENCODER_EVENTS, strict=False))
        if connect:
            self.connect()

    def connect(self):
        if self.RE_PORT == 'COM#':
            return
        m = RotaryEncoderModule(self.RE_PORT)
        m.set_zero_position()  # Not necessarily needed
        m.set_thresholds(self.SET_THRESHOLDS)
        m.enable_thresholds(self.ENABLE_THRESHOLDS)
        m.enable_evt_transmission()
        m.close()


def sound_device_factory(output: Literal['xonar', 'harp', 'hifi', 'sysdefault'] = 'sysdefault', samplerate: int | None = None):
    """
    Will import, configure, and return sounddevice module to play sounds using onboard sound card.
    Parameters
    ----------
    output
        defaults to "sysdefault", should be 'xonar' or 'harp'
    samplerate
        audio sample rate, defaults to 44100
    """
    match output:
        case 'xonar':
            samplerate = samplerate if samplerate is not None else 192000
            devices = sd.query_devices()
            sd.default.device = next((i for i, d in enumerate(devices) if 'XONAR SOUND CARD(64)' in d['name']), None)
            sd.default.latency = 'low'
            sd.default.channels = 2
            channels = 'L+TTL'
            sd.default.samplerate = samplerate
        case 'harp':
            samplerate = samplerate if samplerate is not None else 96000
            sd.default.samplerate = samplerate
            sd.default.channels = 2
            channels = 'stereo'
        case 'hifi':
            samplerate = samplerate if samplerate is not None else 192000
            channels = 'stereo'
        case 'sysdefault':
            samplerate = samplerate if samplerate is not None else 44100
            sd.default.latency = 'low'
            sd.default.channels = 2
            sd.default.samplerate = samplerate
            channels = 'stereo'
        case _:
            raise ValueError()
    return sd, samplerate, channels


def restart_com_port(regexp: str) -> bool:
    """
    Restart the communication port(s) matching the specified regular expression.

    Parameters
    ----------
    regexp : str
        A regular expression used to match the communication port(s).

    Returns
    -------
    bool
        Returns True if all matched ports are successfully restarted, False otherwise.

    Raises
    ------
    NotImplementedError
        If the operating system is not Windows.

    FileNotFoundError
        If the required 'pnputil.exe' executable is not found.

    Examples
    --------
    >>> restart_com_port("COM3")  # Restart the communication port with serial number 'COM3'
    True

    >>> restart_com_port("COM[1-3]")  # Restart communication ports with serial numbers 'COM1', 'COM2', 'COM3'
    True
    """
    if not os.name == 'nt':
        raise NotImplementedError('Only implemented for Windows OS.')
    if not (file_pnputil := Path(shutil.which('pnputil'))).exists():
        raise FileNotFoundError('Could not find pnputil.exe')
    result = []
    for port in list_ports.grep(regexp):
        pnputil_output = subprocess.check_output([file_pnputil, '/enum-devices', '/connected', '/class', 'ports'])
        instance_id = re.search(rf'(\S*{port.serial_number}\S*)', pnputil_output.decode())
        if instance_id is None:
            continue
        result.append(
            subprocess.check_call(
                [file_pnputil, '/restart-device', f'"{instance_id.group}"'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )
            == 0
        )
    return all(result)
