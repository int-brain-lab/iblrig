import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from serial import Serial, SerialException
from serial.tools import list_ports
from serial_singleton import SerialSingleton, filter_ports

from iblrig.path_helper import load_settings_yaml
from iblutil.util import setup_logger

log = setup_logger('iblrig', level='DEBUG')


@dataclass
class TestResult:
    status: Literal['PASS', 'INFO', 'FAIL'] = 'FAIL'
    message: str = ''
    ext_message: str = ''
    solution: str = ''
    url: str = ''
    exception: Exception | None = None


class TestHardwareException(Exception):
    def __init__(self, results: TestResult):
        super().__init__(results.message)
        self.results = results


class TestHardware(ABC):
    log_results: bool = True
    raise_fail_as_exception: bool = False

    def __init__(self, iblrig_settings=None, hardware_settings=None):
        self.iblrig_settings = iblrig_settings or load_settings_yaml('iblrig_settings.yaml')
        self.hardware_settings = hardware_settings or load_settings_yaml('hardware_settings.yaml')

    @abstractmethod
    def _run(self):
        ...

    def run(self, *args, **kwargs):
        self.process(self._run(*args, **kwargs))

    def process(self, results: TestResult) -> None:
        if self.log_results:
            match results.status:
                case 'PASS':
                    log_level = logging.INFO
                    log_symbol = '✔'
                case 'INFO':
                    log_level = logging.INFO
                    log_symbol = 'i'
                case 'WARN':
                    log_level = logging.WARNING
                    log_symbol = '!'
                case 'FAIL':
                    log_level = logging.CRITICAL
                    log_symbol = '✘'
                case _:
                    log_level = 'critical'
                    log_symbol = '?'
            log.log(log_level, f' {log_symbol}  {results.message}.')

        if self.raise_fail_as_exception and results.status == 'FAIL':
            if results.exception is not None:
                raise TestHardwareException(results) from results.exception
            else:
                raise TestHardwareException(results)


class TestHardwareDevice(TestHardware):
    device_name: str

    @abstractmethod
    def _run(self):
        ...

    def __init__(self, *args, **kwargs):
        if self.log_results:
            log.info(f'Running hardware tests for {self.device_name}:')
        super().__init__(*args, **kwargs)


class TestSerialDevice(TestHardwareDevice):
    port: str
    port_properties: None | dict[str, Any]
    serial_queries: None | dict[tuple[object, int], bytes]

    def _run(self) -> TestResult:
        if self.port is None:
            result = TestResult('FAIL', f'No serial port defined for {self.device_name}')
        elif next((p for p in list_ports.comports() if p.device == self.port), None) is None:
            result = TestResult('FAIL', f'`{self.port}` is not a valid serial port')
        else:
            try:
                Serial(self.port, timeout=1).close()
            except SerialException as e:
                result = TestResult('FAIL', f'`{self.port}` cannot be connected to', exception=e)
            else:
                result = TestResult('PASS', f'`{self.port}` is a valid serial port that can be connected to')
        self.process(result)

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
            result = TestResult('PASS', f'Device on `{self.port}` does in fact seem to be a {self.device_name}')
        else:
            result = TestResult('FAIL', f'Device on `{self.port}` does NOT seem to be a {self.device_name}')
        self.process(result)

        return result


class TestRotaryEncoder(TestSerialDevice):
    device_name = 'Rotary Encoder Module'
    port_properties = {'vid': 0x16C0}
    serial_queries = {(b'Q', 2): b'^..$', (b'P00', 1): b'\x01'}

    @property
    def port(self):
        return self.hardware_settings['device_rotary_encoder']['COM_ROTARY_ENCODER']

    def _run(self):
        super().run()
