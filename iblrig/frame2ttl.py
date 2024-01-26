import logging
import struct
import time
from functools import singledispatch

import numpy as np
from serial.serialutil import SerialTimeoutException
from serial.tools.list_ports import comports
from serial_singleton import SerialSingleton

log = logging.getLogger(__name__)


class Frame2TTL(SerialSingleton):
    def __init__(self, port: str, threshold_dark: int = -150, threshold_light: int = 100, **kwargs) -> None:
        # identify micro-controller
        port_info = next((p for p in comports() if p.device == port), None)
        if port_info is not None:
            is_samd21mini = port_info.vid == 0x1B4F and port_info.pid in [0x8D21, 0x0D21]
            is_teensy = port_info.vid == 0x16C0 and port_info.pid == 0x0483
            if not is_samd21mini and not is_teensy:
                raise OSError(f'Device on {port} is not a Frame2TTL')

        # override default arguments of super-class
        kwargs['baudrate'] = 115200
        kwargs['timeout'] = 0.5
        kwargs['write_timeout'] = 0.5

        # initialize super class
        super().__init__(port=port, **kwargs)
        self.flushInput()
        self.flushOutput()

        # detect SAMD21 Mini Breakout (Frame2TTL v1)
        if is_samd21mini and port_info.pid == 0x0D21:
            raise OSError(
                f'SAMD21 Mini Breakout on {self.portstr} is in bootloader '
                f'mode. Unplugging and replugging the device should '
                f'alleviate the issue. If not, try reflashing the Frame2TTL '
                f'firmware.'
            )

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
            self.hw_version = self.query('#', 'B')[0]

        # get firmware version
        try:
            self.fw_version = self.query('F', 'B')[0]
        except struct.error:
            self.fw_version = 1

        # set baud-rates
        if self.hw_version == 3 and self.fw_version == 3:
            self.baudrate = 480000000

        # increase timeout
        self.timeout = 5

        # initialize members
        self._threshold_dark = threshold_dark
        self._threshold_light = threshold_light
        self.set_thresholds(self._threshold_dark, self._threshold_light)
        self._is_streaming = False
        match self.hw_version:
            case 1:
                self._unit_str = 'μs'
                self._dtype_streaming = np.uint32
            case _:
                self._unit_str = 'bits/ms'
                self._dtype_streaming = np.uint16

        # log status
        log.debug(f'Connected to Frame2TTL v{self.hw_version} on port {self.portstr}. ' f'Firmware Version: {self.fw_version}.')

    @property
    def streaming(self) -> bool:
        return self._is_streaming

    @streaming.setter
    def streaming(self, state: bool):
        self.write(struct.pack('<c?', b'S', state))
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
        return self._threshold_dark

    @threshold_light.setter
    def threshold_light(self, value: int) -> None:
        self.set_thresholds(dark=self._threshold_dark, light=value)

    def set_thresholds(self, dark: int, light: int):
        self._threshold_dark = dark
        self._threshold_light = light
        self.write(struct.pack('<cHH' if self.hw_version == 1 else '<chh', b'T', self._threshold_dark, self._threshold_light))
        log.debug(f'Thresholds set to {self._threshold_dark} (dark) and {self._threshold_light} (light)')

    def handshake(self, raise_on_fail: bool = False) -> bool:
        self.flushInput()
        self.write(b'C')
        status = self.read() == bytes([218])
        if not status and raise_on_fail:
            raise OSError(f'Device on {self.portstr} is not a Frame2TTL')
        return status

    def sample(self, n_samples: int) -> np.array:
        buffer = bytearray(n_samples * self._dtype_streaming().itemsize)
        original_timeout = self.timeout
        self.timeout = None
        self.streaming = True
        self.readinto(buffer)
        self.streaming = False
        self.timeout = original_timeout
        return np.frombuffer(buffer, dtype=self._dtype_streaming)

    def calibrate_dark(self, n_samples: int = 1000) -> int:
        if self.hw_version > 1:
            (self._threshold_dark,) = self.query('D', '<h')
        else:
            values = self.sample(n_samples=n_samples)
            self.threshold_dark = int(np.floor(np.min(values)))
        return self._threshold_dark

    def calibrate_light(self, n_samples: int = 1000) -> int:
        if self.hw_version > 1:
            (self._threshold_light,) = self.query('L', '<h')
        else:
            values = self.sample(n_samples=n_samples)
            self.threshold_light = int(np.ceil(np.min(values)))
        return self._threshold_light