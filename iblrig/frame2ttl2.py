import struct

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import QPoint
from serial import Serial
from serial.tools.list_ports import comports
from serial.serialutil import SerialTimeoutException
import logging
from usb.core import find as find_device

import numpy as np

logger = logging.getLogger(__name__)


class Frame2TTL(Serial):

    def __init__(self, *args, **kwargs) -> None:

        # override default arguments of super-classde
        if "baudrate" not in kwargs:
            kwargs["baudrate"] = 115200
        if "timeout" not in kwargs:
            kwargs["timeout"] = 0.5
        if "write_timeout" not in kwargs:
            kwargs["write_timeout"] = 0.5

        super().__init__(*args, **kwargs)
        self.flushInput()
        self.flushOutput()

        self._streaming = False
        self._calibration_timer = QtCore.QBasicTimer()

        # get more information on USB device
        port_info = next((p for p in comports() if p.device==self.portstr), None)
        if not port_info or not port_info.vid:
            raise IOError(f'Device on {self.portstr} is not a Frame2TTL')

        # detect SAMD21 Mini Breakout (Frame2TTL v1)
        is_samd21mini = port_info.vid==0x1B4F and port_info.pid in [0x8D21, 0x0D21]
        if is_samd21mini and port_info.pid==0x0D21:
            raise IOError(f'SAMD21 Mini Breakout on {self.portstr} is in bootloader '
                          f'mode. Unplugging and replugging the device should '
                          f'alleviate the issue. If not, try reflashing the Frame2TTL '
                          f'firmware.')

        # try to connect and identify Frame2TTL
        try:
            self.flushInput()
            self.write(b'C')
        except SerialTimeoutException as e:
            if is_samd21mini:
                dev = find_device(idVendor=port_info.vid, idProduct=port_info.pid)
                raise IOError(f'Writing to {self.portstr} timed out. This is a known '
                              f'problem with the SAMD21 mini breakout used by '
                              f'Frame2TTL v1. Unplugging and replugging the device is '
                              f'the only known fix.') from e
            else:
                raise e
        if self.read()!=bytes([218]):
            raise IOError(f'Device on {self.portstr} is not a Frame2TTL')

        # get hardware version
        if is_samd21mini:
            self.hw_version = 1
        else:
            self.write('#')
            self.hw_version = self.read()

    @property
    def streaming(self) -> bool:
        return self._streaming

    @streaming.setter
    def streaming(self, state: bool):
        self.write(struct.pack('<c?', b'S', bool))
        self.reset_input_buffer()
        self._streaming = state

    def sample(self, n_samples: int) -> np.array:
        samples = np.array([])
        bytes_to_read = min(n_samples * 4, 4096)

        # self.streaming = True

        # self.reset_input_buffer()
        while bytes_to_read > 0:
            if self.in_waiting >= bytes_to_read:
                samples = np.append(samples, np.frombuffer(self.read(bytes_to_read), 'uint32'))
                bytes_to_read = min(len(samples) * 4 - bytes_to_read, 4096)

        # self.streaming = False
        # self.reset_input_buffer()
        print(n_samples)
        return samples[0:n_samples]

    def calibration(self,
                    color: tuple[int, int, int] = (0, 0, 0),
                    screen: int = 0,
                    size: int = 100,
                    n_samples: int = 2000) -> np.array:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        win = _Calibrator(frame2ttl=self, color=color, screen=screen, size=size, n_samples=n_samples)
        app.exec_()
        return win.data


class _Calibrator(QDialog):

    def __init__(self,
                 frame2ttl: Frame2TTL,
                 color: tuple[int, int, int],
                 screen: int,
                 size: int,
                 n_samples: int,
                 *args,
                 **kwargs) -> np.array:
        self.f2ttl = frame2ttl
        self.color = color
        self.n_samples = n_samples

        self.data: np.array = None
        self.state = 0

        # display frameless QDialog with given color
        super().__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFixedSize(size, size)
        x, y, w, h = QApplication.desktop().screenGeometry(screen).getRect()
        self.move(QPoint(x + w - size, y + h - size))
        self.setStyleSheet(f"background: rgb{self.color}")
        self.show()

        # call measuring routine
        QtCore.QTimer.singleShot(250, self._measure)

    def _measure(self):
        self.f2ttl.flushInput()
        self.f2ttl.streaming = True
        self.data = self.f2ttl.sample(n_samples=self.n_samples)
        self.f2ttl.streaming = False
        self.close()
