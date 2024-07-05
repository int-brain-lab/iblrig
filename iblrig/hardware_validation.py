import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from inspect import isabstract
from math import isclose
from struct import unpack
from typing import Any, cast

import numpy as np
import sounddevice
import usb
from dateutil.relativedelta import relativedelta
from serial import Serial, SerialException
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

from iblrig.base_tasks import BpodMixin, SoundMixin
from iblrig.constants import BASE_PATH, HAS_PYSPIN, HAS_SPINNAKER, IS_GIT
from iblrig.hardware import Bpod
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings
from iblrig.serial_singleton import SerialSingleton, filter_ports
from iblrig.tools import ANSI, get_inheritors, internet_available
from iblrig.version_management import get_branch, is_dirty
from pybpodapi.bpod_modules.bpod_module import BpodModule
from pybpodapi.state_machine import StateMachine

log = logging.getLogger(__name__)


class Status(IntEnum):
    """Possible status codes of hardware validations"""

    PEND = 0  # Test pending
    SKIP = 1  # Test not applicable (e.g., device not present)
    PASS = 2  # Test passed
    WARN = 3  # Test passed with warning
    INFO = 4  # Secondary information yielded from tests (e.g., firmware version)
    FAIL = 5  # Test failed


@dataclass
class Result:
    """Dataclass holding the results of a single validation"""

    status: Status
    message: str
    ext_message: str | None = None
    solution: str | None = None
    url: str | None = None
    exception: Exception | None = None


class ValidateHardwareError(Exception):
    def __init__(self, results: Result):
        super().__init__(results.message)
        self.results = results


class Validator(ABC):
    log_results: bool = True
    raise_fail_as_exception: bool = False
    interactive: bool
    iblrig_settings: RigSettings
    hardware_settings: HardwareSettings
    _name: str | None = None

    def __init__(
        self,
        iblrig_settings: RigSettings | None = None,
        hardware_settings: HardwareSettings | None = None,
        interactive: bool = False,
    ):
        self.iblrig_settings = iblrig_settings or load_pydantic_yaml(RigSettings)
        self.hardware_settings = hardware_settings or load_pydantic_yaml(HardwareSettings)
        self.interactive = interactive

    @property
    def name(self) -> str:
        return getattr(self, '_name', self.__class__.__name__)

    @abstractmethod
    def _run(self, *args, **kwargs) -> Generator[Result, None, bool]: ...

    def run(self, *args, **kwargs) -> Generator[Result, None, bool]:
        success = yield from self._run(*args, **kwargs)
        return success

    def _get_bpod(self) -> Generator[Result, None, Bpod | None]:
        if self.hardware_settings.device_bpod.COM_BPOD is None:
            yield Result(Status.INFO, f'Cannot complete validation of {self.name} without Bpod')
            return None
        try:
            return Bpod(self.hardware_settings.device_bpod.COM_BPOD, skip_initialization=True)
        except Exception as e:
            yield Result(Status.FAIL, f'Cannot complete validation of {self.name}: connection to Bpod failed', exception=e)
            return None

    def _get_module(self, module_name: str, bpod: Bpod | None = None) -> Generator[Result, None, BpodModule | None]:
        if bpod is None:
            bpod = yield from self._get_bpod()
        if bpod is None:
            return None

        module = None if bpod.modules is None else next((m for m in bpod.modules if m.name.startswith(module_name)), None)

        if module is not None:
            yield Result(Status.PASS, f'{self.name} is connected to Bpod on module port #{module.serial_port}')
            yield Result(Status.INFO, f'Firmware Version: {module.firmware_version}')
            return module
        else:
            yield Result(
                Status.FAIL,
                f"{self.name} is not connected to Bpod's module port",
                solution=f"Connect {self.name} to one of Bpod's module ports",
            )
            return None

    def process(self, results: Result) -> Result:
        if self.log_results:
            match results.status:
                case Status.PASS:
                    log_level = logging.INFO
                case Status.INFO:
                    log_level = logging.INFO
                case Status.FAIL:
                    log_level = logging.CRITICAL
                case _:
                    log_level = logging.CRITICAL
            log.log(log_level, results.message)

        if self.raise_fail_as_exception and results.status == Status.FAIL:
            if results.exception is not None:
                raise ValidateHardwareError(results) from results.exception
            else:
                raise ValidateHardwareError(results)

        return results


class ValidatorSerial(Validator):
    port_properties: dict[str, Any] = {}
    serial_queries: None | dict[tuple[object, int], bytes] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    @abstractmethod
    def port(self) -> str | None: ...

    @property
    def port_info(self) -> ListPortInfo | None:
        return next(list_ports.grep(self.port), None) if self.port is not None else None

    def _run(self):
        if self.port is None:
            yield Result(Status.SKIP, f'No serial port defined for {self.name}')
            return False
        elif next((p for p in list_ports.comports() if p.device == self.port), None) is None:
            yield Result(
                Status.FAIL,
                f'{self.port} is not a valid serial port',
                solution='Check serial port setting in hardware_settings.yaml',
            )
            return False
        else:
            try:
                Serial(self.port, timeout=1).close()
                yield Result(Status.PASS, f'Serial device on {self.port} can be connected to')
                yield Result(
                    Status.INFO,
                    f'USB ID: {self.port_info.vid:04X}:{self.port_info.pid:04X}, '
                    f'Serial Number: {self.port_info.serial_number}',
                )
            except SerialException as e:
                yield Result(
                    Status.FAIL,
                    f'{self.name} on {self.port} cannot be connected to',
                    solution='Try power-cycling the device',
                    exception=e,
                )
                return False

        # first, test for properties of the serial port without opening the latter (VID, PID, etc)
        passed = (
            self.port in filter_ports(**self.port_properties) if getattr(self, 'port_properties', None) is not None else False
        )

        # query the devices for characteristic responses
        if passed and getattr(self, 'serial_queries', None) is not None:
            with Serial(self.port, timeout=1) as ser:
                for query, regex_pattern in self.serial_queries.items():
                    ser.write(query[0])
                    return_string = ser.read(query[1])
                    ser.flush()
                    if not (passed := bool(re.search(regex_pattern, return_string))):
                        break

        if passed:
            yield Result(Status.PASS, f'Serial device positively identified as {self.name}')
            return True
        else:
            yield Result(
                Status.FAIL,
                f'Serial device on {self.port} does NOT seem to be a {self.name}',
                solution='Check serial port setting in hardware_settings.yaml',
            )
            return False


class ValidatorRotaryEncoderModule(ValidatorSerial):
    _name = 'Bpod Rotary Encoder Module'
    port_properties = {'vid': 0x16C0}
    serial_queries = {(b'Q', 2): b'^..$', (b'P00', 1): b'\x01'}

    @property
    def port(self):
        return self.hardware_settings.device_rotary_encoder.COM_ROTARY_ENCODER

    def _run(self):
        # invoke ValidateSerialDevice._run()
        success = yield from super()._run()
        if not success:
            return False

        # obtain hardware version
        with SerialSingleton(self.port, timeout=0.1) as ser:
            v = '1.x' if ser.query(b'Ix', 1) == b'\x01' else '2+'
        yield Result(Status.INFO, f'Hardware Version: {v}')

        # try to get Bpod
        bpod = yield from self._get_bpod()
        if not bpod:
            return False

        # try to get Bpod module
        module = yield from self._get_module('RotaryEncoder', bpod)
        if not module:
            return False

        # log_fun('info', f'firmware version: {bpod.modules[0].firmware_version}')
        #
        # s.write(b'Z')
        # p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
        # log_fun('warn', "please move the wheel to the left (animal's POV) by a quarter turn")
        # while np.abs(p) < 200:
        #     p = np.frombuffer(query(s, b'Q', 2), dtype=np.int16)[0]
        # if p > 0:
        #     log_fun('fail', 'Rotary encoder seems to be wired incorrectly - try swapping A and B', last=True)
        # else:
        #     log_fun('pass', 'rotary encoder is wired correctly', last=True)
        # s.close()


# class ValidatorScreen(Validator):
#     device_name = 'Screen'
#
#     def _run(self):
#         pass
#         # if os.name == 'nt':
#         #     import ctypes
#         #
#         #     from win32api import EnumDisplayMonitors, EnumDisplaySettingsEx, GetMonitorInfo
#         #
#         #     display_idx = self.hardware_settings.device_screen.DISPLAY_IDX
#         #     monitors = EnumDisplayMonitors()
#         #     monitor = monitors[display_idx]
#         #     display_handle = monitor[0]
#         #     scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(display_idx)
#         #     display_info = GetMonitorInfo(display_handle)
#         #     display_settings = EnumDisplaySettingsEx(display_info['Device'])
#         #     # TODO: Implementation ...


class ValidatorAmbientModule(Validator):
    _name = 'Bpod Ambient Module'

    def _run(self):
        # yield Bpod's connection status
        bpod = yield from self._get_bpod()
        if bpod is None:
            return False

        # yield module's connection status
        module = yield from self._get_module('AmbientModule', bpod)
        if module is None:
            return False

        # yield sensor values
        module.start_module_relay()
        bpod.bpod_modules.module_write(module, 'R')
        (t, p, h) = unpack('3f', bytes(bpod.bpod_modules.module_read(module, 12)))
        module.stop_module_relay()
        yield Result(Status.INFO, f'Temperature: {t:.1f} °C')
        yield Result(Status.INFO, f'Air pressure: {p / 100:.1f} mbar')
        yield Result(Status.INFO, f'Rel. humidity: {h:.1f}%')
        return True


class ValidatorBpod(ValidatorSerial):
    _name = 'Bpod'
    port_properties = {'vid': 0x16C0}
    serial_queries = {(b'6', 1): b'5'}

    @property
    def port(self):
        return self.hardware_settings.device_bpod.COM_BPOD

    def _run(self):
        # close existing Bpod singleton
        if (bpod := Bpod._instances.get(self.hardware_settings.device_bpod.COM_BPOD, None)) is not None:  # noqa
            bpod.close()

        # invoke ValidateSerialDevice._run()
        success = yield from super()._run()
        if not success:
            return False

        # check hardware and firmware version
        with SerialSingleton(self.hardware_settings.device_bpod.COM_BPOD) as ser:
            v_major, machine_type = ser.query(b'F', '<2H')
            firmware_version = (v_major, ser.query(b'f', '<H')[0] if v_major > 22 else 0)
            machine_str = {1: 'v0.5', 2: 'r07+', 3: 'r2.0-2.5', 4: '2+ r1.0'}[machine_type]
            machine_str.join(f", PCB revision{ser.query(b'v', '<B')[0]}" if v_major > 22 else '')
        yield Result(Status.INFO, f'Hardware version: {machine_str}')
        yield Result(Status.INFO, f'Firmware version: {firmware_version[0]}.{firmware_version[1]}')
        if firmware_version[0] > 22:
            yield Result(
                Status.FAIL,
                'Firmware version greater than 22 are not supported by IBLRIG',
                solution='Downgrade the Bpod' 's firmware to version 22',
            )
            return False

        # try to connect to Bpod
        try:
            bpod = Bpod(self.hardware_settings.device_bpod.COM_BPOD, skip_initialization=False)
            yield Result(Status.PASS, 'Successfully connected to Bpod using pybpod')
        except Exception as e:
            yield Result(
                Status.FAIL, 'Could not connect to Bpod using pybpod', solution='Try power-cycling the Bpod', exception=e
            )
            return False

        # return connected modules
        for module in bpod.modules:
            if module.connected:
                yield Result(Status.INFO, f'Module on port #{module.serial_port}: "{module.name}"')
        return True


class ValidatorCamera(Validator):
    _name = 'Camera'

    def _run(self):
        if self.hardware_settings.device_cameras is None or (
            isinstance(self.hardware_settings.device_cameras, dict) and len(self.hardware_settings.device_cameras) == 0
        ):
            yield Result(Status.SKIP, 'No cameras defined in hardware_settings.yaml - skipping validation')
            return False

        if HAS_SPINNAKER:
            yield Result(Status.PASS, 'Spinnaker SDK is installed')
        else:
            yield Result(
                Status.WARN, 'Spinnaker SDK is not installed', solution='Use install_spinnaker command to install Spinnaker SDK'
            )

        if HAS_PYSPIN:
            yield Result(Status.PASS, 'PySpin is installed')
        else:
            yield Result(Status.WARN, 'PySpin is not installed', solution='Use install_pyspin command to install PySpin')

        if HAS_SPINNAKER and HAS_PYSPIN:
            from iblrig.video_pyspin import Cameras, enable_camera_trigger

            with Cameras() as cameras:
                if len(cameras) == 0:
                    yield Result(
                        Status.FAIL,
                        'Could not find a camera connected to the computer',
                        solution='Connect a camera on one of the computers USB ports',
                    )
                    return False
                else:
                    yield Result(
                        Status.PASS, f'Found {len(cameras)} camera{"s" if len(cameras) > 1 else ""} connected to the computer'
                    )
                    for idx in range(len(cameras)):
                        yield Result(
                            Status.INFO,
                            f'Camera {idx}: {cameras[idx].DeviceModelName.ToString()}, '
                            f'Serial #{cameras[idx].DeviceID.ToString()}',
                        )
                        enable_camera_trigger(enable=False, camera=cameras[idx])

        # yield Bpod's connection status
        bpod = yield from self._get_bpod()
        if bpod is None:
            return False

        sma = StateMachine(bpod)
        sma.add_state(state_name='collect', state_timer=0.2, state_change_conditions={'Tup': 'exit'})
        bpod.send_state_machine(sma)
        bpod.run_state_machine(sma)
        triggers = [i.host_timestamp for i in bpod.session.current_trial.events_occurrences if i.content == 'Port1In']
        if len(triggers) == 0:
            yield Result(
                Status.FAIL,
                "No TTL detected on Bpod's behavior port #1",
                solution='Check the wiring between camera and valve driver board and make sure the latter is connected '
                "to Bpod's behavior port #1",
            )
            return False
        else:
            yield Result(Status.PASS, "Detected camera TTL on Bpod's behavior port #1")
            trigger_rate = np.mean(1 / np.diff(triggers))
            target_rate = 30
            if isclose(trigger_rate, target_rate, rel_tol=0.1):
                yield Result(Status.PASS, f'Measured TTL rate: {trigger_rate:.1f} Hz')
            else:
                yield Result(Status.WARN, f'Measured TTL rate: {trigger_rate:.1f} Hz (expecting {target_rate} Hz)')
        return True


class ValidatorAlyx(Validator):
    _name = 'Alyx'

    def _run(self):
        # Validate ALYX_URL
        if self.iblrig_settings.ALYX_URL is None:
            yield Result(Status.SKIP, 'ALYX_URL has not been set in hardware_settings.yaml - skipping validation')
            return False
        elif not internet_available(timeout=2, force_update=True):
            yield Result(
                Status.FAIL, f'Cannot connect to {self.iblrig_settings.ALYX_URL.host}', solution='Check your Internet connection'
            )
            return False
        elif not internet_available(host=self.iblrig_settings.ALYX_URL.host, port=443, timeout=2, force_update=True):
            yield Result(
                Status.FAIL,
                f'Cannot connect to {self.iblrig_settings.ALYX_URL.host}',
                solution='Check ALYX_URL in hardware_settings.yaml and make sure that your computer is allowed to connect',
            )
            return False
        else:
            yield Result(Status.PASS, f'{self.iblrig_settings.ALYX_URL.host} can be connected to')

        # Validate ALYX_LAB
        if self.iblrig_settings.ALYX_LAB is None:
            yield Result(Status.FAIL, 'ALYX_LAB has not been set', solution='Set ALYX_LAB in hardware_settings.yaml')
        return True


class ValidatorValve(Validator):
    _name = 'Valve'

    def _run(self):
        calibration_date = self.hardware_settings.device_valve.WATER_CALIBRATION_DATE
        today = date.today()
        delta_warn = relativedelta(months=1)
        delta_fail = relativedelta(months=3)
        days_passed = (today - calibration_date).days
        if calibration_date > date.today():
            yield Result(Status.FAIL, 'Date of last valve calibration is in the future', solution='Calibrate valve')
        elif calibration_date + delta_warn < today:
            yield Result(Status.WARN, f'Valve has not been calibrated in {days_passed} days', solution='Calibrate valve')
        elif calibration_date + delta_fail < date.today():
            yield Result(Status.FAIL, f'Valve has not been calibrated in {days_passed} days', solution='Calibrate valve')
        elif days_passed > 1:
            yield Result(Status.PASS, f'Valve has been calibrated {days_passed} days ago')
        else:
            yield Result(Status.PASS, f'Valve has been calibrated {"yesterday" if days_passed==1 else "today"}')


class ValidatorMic(Validator):
    _name = 'Microphone'

    def _run(self):
        if self.hardware_settings.device_microphone is None:
            yield Result(Status.SKIP, 'No workflow defined for microphone')
            return False

        sounddevice._terminate()
        sounddevice._initialize()

        devices = [d for d in sounddevice.query_devices() if 'UltraMic 200K' in d.get('name', '')]
        if len(devices) > 0:
            yield Result(Status.PASS, 'Found UltraMic 200K microphone')
            return True
        else:
            yield Result(
                Status.FAIL,
                'Could not find UltraMic 200K microphone',
                solution='Make sure that the microphone is connected to the PC via USB',
            )
            return False


class ValidatorGit(Validator):
    _name = 'Git'

    def _run(self):
        if not IS_GIT:
            yield Result(Status.SKIP, 'Your copy of IBLRIG is not managed through Git')
            return False

        return_status = True
        main_branch = 'iblrigv8'
        this_branch = get_branch()
        if this_branch != main_branch:
            yield Result(
                Status.WARN,
                f"Working tree of IBLRIG is on Git branch '{this_branch}'",
                solution=f"Issue 'git checkout {main_branch}' to switch to '{main_branch}' branch",
            )
            return_status = False
        else:
            yield Result(Status.PASS, f"Working tree of IBLRIG is on Git branch '{main_branch}'")

        if is_dirty():
            yield Result(
                Status.WARN,
                "Working tree of IBLRIG contains local changes - don't expect things to work as intended!",
                solution="To list files that have been changed locally, issue 'git diff --name-only'. "
                "Issue 'git reset --hard' to reset the repository to its default state",
            )
            return_status = False
        else:
            yield Result(Status.PASS, 'Working tree of IBLRIG does not contain local changes')

        return return_status


class _SoundCheckTask(BpodMixin, SoundMixin):
    protocol_name = 'hardware_check_harp'

    def __init__(self, *args, **kwargs):
        param_file = BASE_PATH.joinpath('iblrig', 'base_choice_world_params.yaml')
        super().__init__(*args, task_parameter_file=param_file, **kwargs)

    def start_hardware(self):
        self.start_mixin_bpod()
        self.start_mixin_sound()

    def get_state_machine(self):
        sma = StateMachine(self.bpod)
        sma.add_state('tone', 0.5, {'Tup': 'exit'}, [self.bpod.actions.play_tone])
        return sma

    def _run(self):
        pass

    def create_session(self):
        pass


class ValidatorSound(ValidatorSerial):
    _name = 'Sound'
    _module_name: str | None = None

    def __init__(self, *args, **kwargs):
        output_type = kwargs['hardware_settings'].device_sound.OUTPUT
        match output_type:
            case 'harp':
                self._name = 'HARP Sound Card'
                self._module_name = 'SoundCard'
                self.port_properties = {'vid': 0x0403, 'pid': 0x6001}
            case 'hifi':
                self._name = 'Bpod HiFi Module'
                self._module_name = 'HiFi'
                self.serial_queries = {(b'\xf3', 1): b'\xf4'}
                self.port_properties = {'vid': 0x16C0, 'pid': 0x0483}
            case 'xonar':
                self._name = 'Xonar Sound Card'
        if output_type in ['harp', 'hifi']:
            super().__init__(*args, **kwargs)  # call ValidatorSerial.__init__()
        else:
            super(ValidatorSerial, self).__init__(*args, **kwargs)  # call Validator.__init__()

    @property
    def port(self) -> str | None:
        match self.hardware_settings.device_sound.OUTPUT:
            case 'harp':
                return (
                    com_port
                    if (com_port := self.hardware_settings.device_sound.COM_SOUND) is not None
                    else next(filter_ports(**self.port_properties), None)
                )
            case 'hifi':
                return self.hardware_settings.device_sound.COM_SOUND
            case _:
                return None

    def _run(self):
        if (success := self.hardware_settings.device_sound.OUTPUT) == 'sysdefault':
            yield Result(
                Status.FAIL,
                "Sound output device 'sysdefault' is intended for testing purposes only",
                solution="Set device_sound.OUTPUT to 'hifi', 'harp' or 'xonar'",
            )
            return False

        # check serial device
        if self.hardware_settings.device_sound.OUTPUT in ['harp', 'hifi']:
            success = yield from super()._run()
            if not success:
                return False

        # device-specific validations
        match self.hardware_settings.device_sound.OUTPUT:
            case 'harp':
                if (dev := usb.core.find(manufacturer='Champalimaud Foundation', product='Harp Sound Card')) is None:
                    yield Result(
                        Status.FAIL,
                        'Cannot find USB sound device',
                        solution="Connect both of the sound card's USB ports and make sure that the HARP drivers are "
                        'installed',
                    )
                    return False
                else:
                    yield Result(Status.PASS, 'Found USB sound device')
                    yield Result(Status.INFO, f'USB ID: {dev.idVendor:04X}:{dev.idProduct:04X}')

        # yield module's connection status
        if self._module_name is not None:
            module = yield from self._get_module(self._module_name)
            if module is None:
                return False

        # run state machine
        if self.interactive:
            task = _SoundCheckTask(subject='toto')
            task.start_hardware()
            sma = task.get_state_machine()
            task.bpod.send_state_machine(sma)
            yield Result(Status.INFO, 'Playing audible sound - can you hear it?')
            task.bpod.run_state_machine(sma)
            bpod_data = task.bpod.session.current_trial.export()
            if (n_events := len(bpod_data['Events timestamps'].get('BNC2High', []))) == 0:
                yield Result(
                    Status.FAIL,
                    "No event detected on Bpod's BNC In 2",
                    solution="Make sure to connect the sound-card to Bpod's TTL Input 2",
                )
            elif n_events == 1:
                yield Result(Status.PASS, "Detected Event on Bpod's TTL Input 2")
            else:
                yield Result(
                    Status.FAIL,
                    "Multiple events detected on Bpod's BNC Input 2",
                    solution="Make sure to connect the sound-card to Bpod's TTL Input 2",
                )


def get_all_validators() -> list[type[Validator]]:
    return [cast(type[Validator], x) for x in get_inheritors(Validator) if not isabstract(x)]


def run_all_validators(
    iblrig_settings: RigSettings | None = None, hardware_settings: HardwareSettings | None = None, interactive: bool = False
) -> Generator[Result, None, None]:
    validators = get_all_validators()
    for validator in validators:
        yield from validator(iblrig_settings=iblrig_settings, hardware_settings=hardware_settings, interactive=interactive).run()


def run_all_validators_cli():
    validators = get_all_validators()
    fail = 0
    warn = 0
    for validator in validators:
        v = validator()
        print(f'{ANSI.BOLD + ANSI.UNDERLINE + v.name + ANSI.END}')
        for result in v.run():
            if result.status == Status.FAIL:
                color = ANSI.RED + ANSI.BOLD
                fail += 1
            elif result.status == Status.WARN:
                color = ANSI.YELLOW + ANSI.BOLD
                warn += 1
            else:
                color = ANSI.END
            print(f'{color}- {result.message}{ANSI.END}')
            if result.solution is not None and len(result.solution) > 0:
                print(f'{color}  Suggestion: {result.solution}{ANSI.END}')
        print('')
    if fail > 0:
        print(ANSI.RED + ANSI.BOLD + f'{fail} validation{"s" if fail > 1 else ""} failed.')
    if warn > 0:
        print(ANSI.YELLOW + ANSI.BOLD + f'Validations passed with {warn} warning{"s" if warn > 1 else ""}.')
    if warn == 0 and fail == 0:
        print(ANSI.GREEN + ANSI.BOLD + 'All validations were passed - no issues found.')
