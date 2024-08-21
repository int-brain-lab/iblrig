import logging
import struct
import time
from typing import Literal

import numpy as np
from serial.serialutil import SerialTimeoutException
from serial.tools.list_ports import comports

from iblrig.serial_singleton import SerialSingleton

log = logging.getLogger(__name__)


class Frame2TTL(SerialSingleton):
    _threshold_dark: int | None = None
    _threshold_light: int | None = None
    _calibration_stage: int = 0
    _calibrate_light: int | None = None

    def __init__(self, port: str, threshold_light: int | None = None, threshold_dark: int | None = None, **kwargs) -> None:
        # identify micro-controller
        port_info = next((p for p in comports() if p.device == port), None)
        if port_info is not None:
            is_samd21mini = port_info.vid == 0x1B4F and port_info.pid in [0x8D21, 0x0D21]
            is_teensy = port_info.vid == 0x16C0 and port_info.pid == 0x0483
            if not is_samd21mini and not is_teensy:
                raise OSError(f'Device on {port} is not a Frame2TTL')
        else:
            raise OSError(f"Couldn't initialize Frame2TTL on port `{port}` - port not found.")

        # catch SAMD21 in bootloader mode (Frame2TTL v1)
        if is_samd21mini and port_info.pid == 0x0D21:
            raise OSError(
                f'SAMD21 Mini Breakout on {port} is in bootloader mode. ' f'Replugging the device should alleviate the issue.'
            )

        # override default arguments of super-class
        kwargs['baudrate'] = 115200
        kwargs['timeout'] = 0.5
        kwargs['write_timeout'] = 0.5

        # initialize super class
        super().__init__(port=port, **kwargs)

        # try to connect and identify Frame2TTL
        try:
            self.handshake(raise_on_fail=True)
        except SerialTimeoutException as e:
            if is_samd21mini:
                # touch frame2ttl with magic baud rate to trigger a reboot
                log.info(f'Trying to reboot frame2ttl on {self.portstr} ...')
                self.baudrate = 300
                self.close()
                time.sleep(1)

                # try a second handshake
                self.baudrate = kwargs['baudrate']
                self.open()
                try:
                    self.handshake(raise_on_fail=True)
                except SerialTimeoutException as e:
                    raise OSError(
                        f'Writing to {self.portstr} timed out. This is a known '
                        f'problem with the SAMD21 mini breakout used by '
                        f'Frame2TTL v1. Updating the Frame2TTL firmware should '
                        f'alleviate the issue. Alternatively, unplugging and '
                        f'replugging the device should help as well.'
                    ) from e
            else:
                raise e

        # get hardware version
        if is_samd21mini:
            self.hw_version = 1
        else:
            self.hw_version = self.query(query='#', data_specifier='B')[0]

        # get firmware version
        try:
            self.fw_version = self.query(query='F', data_specifier='B')[0]
        except struct.error:
            self.fw_version = 1

        # set baud-rates
        if self.hw_version == 3 and self.fw_version == 3:
            self.baudrate = 480000000

        # increase timeout
        self.timeout = 5

        # log status
        log.debug(f'Connected to Frame2TTL v{self.hw_version} on port {self.portstr}. ' f'Firmware Version: {self.fw_version}.')

        # initialize members
        match self.hw_version:
            case 1:
                self.unit_str = 'μs'
                self._dtype_streaming = np.uint32
            case _:
                self.unit_str = 'bits/ms'
                self._dtype_streaming = np.uint16
        if threshold_dark is None:
            threshold_dark = -150 if self.hw_version > 1 else 40
        if threshold_light is None:
            threshold_light = 100 if self.hw_version > 1 else 80
        self.set_thresholds(light=threshold_light, dark=threshold_dark)
        self._is_streaming = False

    @property
    def streaming(self) -> bool:
        return self._is_streaming

    @streaming.setter
    def streaming(self, state: bool):
        self.write_packed('<c?', b'S', state)
        self.reset_input_buffer()
        self._is_streaming = state

    @property
    def threshold_dark(self) -> int:
        return self._threshold_dark

    @threshold_dark.setter
    def threshold_dark(self, value: int) -> None:
        self.set_thresholds(dark=value, light=self._threshold_light)

    @property
    def threshold_light(self) -> int:
        return self._threshold_light

    @threshold_light.setter
    def threshold_light(self, value: int) -> None:
        self.set_thresholds(dark=self._threshold_dark, light=value)

    def set_thresholds(self, light: int, dark: int):
        self._threshold_dark = dark
        self._threshold_light = light
        self.write_packed('<cHH' if self.hw_version == 1 else '<chh', b'T', self._threshold_light, self._threshold_dark)
        log.debug(f'Thresholds set to {self._threshold_light} (light) and {self._threshold_dark} (dark)')

    def handshake(self, raise_on_fail: bool = False) -> bool:
        self.flushInput()
        status = self.query(query='C', data_specifier='B')[0] == 218
        if not status and raise_on_fail:
            raise OSError(f'Device on {self.portstr} is not a Frame2TTL')
        return status

    def sample(self, n_samples: int) -> np.ndarray:
        buffer = bytearray(n_samples * self._dtype_streaming().itemsize)
        original_timeout = self.timeout
        self.timeout = None
        self.streaming = True
        self.readinto(buffer)
        self.streaming = False
        self.timeout = original_timeout
        return np.frombuffer(buffer, dtype=self._dtype_streaming)

    def calibrate(self, condition: Literal['light', 'dark'], n_samples: int = 1000) -> tuple[int, bool]:
        assert condition in ['light', 'dark'], "stage must be 'light' or 'dark'"
        success = True
        log.debug(f'Calibrating for {condition} condition ...')

        if self.hw_version == 1:
            # TODO: taken from old routine - verify if this makes sense
            values = self.sample(n_samples=n_samples)
            if condition == 'light':
                value = int(np.ceil(np.max(values)))
                self._calibrate_light = value
            else:
                if self._calibrate_light is None:
                    raise ValueError('light threshold needs to be calibrated first')
                value = int(np.floor(np.min(values)))
                if value > self._calibrate_light + 40:
                    value = self._calibrate_light + 40
                else:
                    value = round(self._calibrate_light + (value - self._calibrate_light) / 3)
                    if value < self._calibrate_light + 5:
                        success = False
                self._calibrate_light = None
        else:
            value = self.query(query='L' if condition == 'light' else 'D', data_specifier='<h')[0]
            # TODO: check if readings are sufficiently different

        log.debug(f'Suggested value for {condition} threshold: {value}{self.unit_str}')
        if not success:
            log.error('Calibration failed. Verify that sensor is placed correctly.')
        return value, success
