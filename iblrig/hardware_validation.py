import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from math import isclose
from struct import unpack
from typing import Any

import numpy as np
import requests
from dateutil.relativedelta import relativedelta
from serial import Serial, SerialException
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

from iblrig.constants import HAS_PYSPIN, HAS_SPINNAKER
from iblrig.hardware import Bpod
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings
from iblrig.serial_singleton import SerialSingleton, filter_ports
from iblrig.tools import ANSI, internet_available
from one.webclient import AlyxClient
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
        try:
            return Bpod(self.hardware_settings.device_bpod.COM_BPOD, skip_initialization=True)
        except Exception as e:
            yield Result(Status.FAIL, f'Cannot complete validation of {self.name}: connection to Bpod failed', exception=e)
            return None

    def _get_module(self, module_name: str, bpod: Bpod | None = None) -> Generator[Result, None, BpodModule | None]:
        if bpod is None:
            bpod = yield from self._get_bpod()
        if bpod is None:
            return

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
    port_properties: None | dict[str, Any]
    serial_queries: None | dict[tuple[object, int], bytes]
    port_info: ListPortInfo | None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.port is not None:
            self.port_info = next(list_ports.grep(self.port), None)

    @property
    @abstractmethod
    def port(self) -> str: ...

    def _run(self):
        if self.port is None:
            yield Result(Status.SKIP, f'No serial port defined for {self.name}')
            return False
        elif next((p for p in list_ports.comports() if p.device == self.port), None) is None:
            yield Result(Status.FAIL, f'{self.port} is not a valid serial port', solution='Double check!')
            return False
        else:
            try:
                Serial(self.port, timeout=1).close()
                self.port_info = next(list_ports.grep(self.port), None)
                yield Result(Status.PASS, f'Serial device on {self.port} can be connected to')
                yield Result(
                    Status.INFO,
                    f'USB ID: {self.port_info.vid:04X}:{self.port_info.pid:04X}, '
                    f'Serial Number: {self.port_info.serial_number}',
                )
            except SerialException as e:
                yield Result(Status.FAIL, f'Serial device on {self.port} cannot be connected to', exception=e)
                return False

        # first, test for properties of the serial port without opening the latter (VID, PID, etc)
        passed = self.port in filter_ports(**self.port_properties) if self.port_properties is not None else False

        # query the devices for characteristic responses
        if passed and self.serial_queries is not None:
            with SerialSingleton(self.port, timeout=1) as ser:
                for query, regex_pattern in self.serial_queries.items():
                    return_string = ser.query(*query)
                    ser.flush()
                    if not (passed := bool(re.search(regex_pattern, return_string))):
                        break
        if passed:
            yield Result(Status.PASS, f'Serial device positively identified as {self.name}')
            return True
        else:
            yield Result(Status.FAIL, f'Serial device on {self.port} does NOT seem to be a {self.name}')
            return False


class ValidatorRotaryEncoderModule(ValidatorSerial):
    _name = 'Rotary Encoder Module'
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


class ValidatorScreen(Validator):
    device_name = 'Screen'

    def _run(self):
        pass
        # if os.name == 'nt':
        #     import ctypes
        #
        #     from win32api import EnumDisplayMonitors, EnumDisplaySettingsEx, GetMonitorInfo
        #
        #     display_idx = self.hardware_settings.device_screen.DISPLAY_IDX
        #     monitors = EnumDisplayMonitors()
        #     monitor = monitors[display_idx]
        #     display_handle = monitor[0]
        #     scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(display_idx)
        #     display_info = GetMonitorInfo(display_handle)
        #     display_settings = EnumDisplaySettingsEx(display_info['Device'])
        #     # TODO: Implementation ...


class ValidatorAmbientModule(Validator):
    _name = 'Ambient Module'

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
            yield Result(Status.FAIL, 'Could not connect to Bpod using pybpod', exception=e)
            return False

        # return connected modules
        for module in bpod.modules:
            if module.connected:
                yield Result(Status.INFO, f'Module on port #{module.serial_port}: "{module.name}"')
        return True


class ValidatorCamera(Validator):
    _name = 'Camera'

    def _run(self):
        if self.hardware_settings.device_cameras is None:
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
            yield Result(Status.WARN, 'Spinnaker SDK is not installed', solution='Use install_pyspin command to install PySpin')

        if HAS_SPINNAKER and HAS_PYSPIN:
            from iblrig.video_pyspin import Cameras, enable_camera_trigger

            with Cameras() as cameras:
                if len(cameras) == 0:
                    yield Result(Status.FAIL, 'Could not find a camera connected to the computer')
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
            yield Result(Status.FAIL, 'No triggers detected on Bpod' 's behavior port #1')
            return False
        else:
            yield Result(Status.PASS, "Detected camera triggers on Bpod's behavior port #1")
            trigger_rate = np.mean(1 / np.diff(triggers))
            target_rate = 30
            if isclose(trigger_rate, target_rate, rel_tol=0.1):
                yield Result(Status.PASS, f'Measured trigger rate: {trigger_rate:.1f} Hz')
            else:
                yield Result(Status.WARN, f'Measured trigger rate: {trigger_rate:.1f} Hz')
        return True


class ValidatorAlyx(Validator):
    _name = 'Alyx'

    def _run(self):
        # Validate ALYX_URL
        if self.iblrig_settings.ALYX_URL is None:
            yield Result(Status.SKIP, 'ALYX_URL has not been set in hardware_settings.yaml - skipping validation')
            raise StopIteration(False)
        elif not internet_available(timeout=3, force_update=True):
            yield Result(
                Status.FAIL, f'Cannot connect to {self.iblrig_settings.ALYX_URL.host}', solution='Check your Internet connection'
            )
            return False
        elif not internet_available(host=self.iblrig_settings.ALYX_URL.host, port=443, timeout=3, force_update=True):
            yield Result(
                Status.FAIL,
                f'Cannot connect to {self.iblrig_settings.ALYX_URL.host}',
                solution='Check ALYX_URL in hardware_settings.yaml and make sure that your computer is allowed to connect to it',
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
            yield Result(Status.PASS, f'Valve has been calibrated {"yesterday" if days_passed == 1 else "today"}')


class ValidatorAlyxLabLocation(Validator):
    """
    This class validates that the rig name in hardware_settings.yaml does exist in Alyx.
    """

    def _run(self, alyx: AlyxClient | None = None):
        try:
            if alyx is None:
                alyx = AlyxClient()
            alyx.rest('locations', 'read', id=self.hardware_settings['RIG_NAME'])
            results_kwargs = dict(status=Status.PASS, message='')
        except requests.exceptions.HTTPError as ex:
            if ex.response.status_code not in (404, 400):  # file not found; auth error
                # Likely Alyx is down or server-side issue
                log.warning('Failed to determine lab location on Alyx')
                log.debug('%s', ex.response)
                results_kwargs = dict(
                    status=Status.FAIL, message='Failed to determine lab location on Alyx', solution='Check if Alyx is reachable'
                )
                self.raise_fail_as_exception = False
            else:
                error_message = f'Could not find rig name {self.hardware_settings["RIG_NAME"]} in Alyx'
                solution = (
                    f"Please check the RIG_NAME key in hardware_settings.yaml and make sure it is created in Alyx here: "
                    f'{self.iblrig_settings["ALYX_URL"]}/admin/misc/lablocation/'
                )
                results_kwargs = dict(status=Status.FAIL, message=error_message, solution=solution)
                self.raise_fail_as_exception = True
        return Result(**results_kwargs)


def get_all_validators() -> list[type[Validator]]:
    # return [x for x in get_inheritors(Validator) if not isabstract(x)]
    return [ValidatorRotaryEncoderModule, ValidatorBpod, ValidatorAmbientModule, ValidatorAlyx, ValidatorCamera, ValidatorValve]


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
