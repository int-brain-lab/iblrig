import logging
import struct
import time

import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QApplication, QDialog
from serial.serialutil import SerialTimeoutException
from serial.tools.list_ports import comports
from serial_singleton import SerialSingleton

log = logging.getLogger(__name__)


def _convert_bonsai_sync_pos(
    x: float = 1.33, y: float = -1.03, extent_x: float = 0.2, extent_y: float = 0.2, w_screen: int = 2048, h_screen: int = 1536
) -> tuple[int, int]:
    w_sync = round(w_screen - (w_screen + (x - extent_x / 2) * h_screen) / 2)
    h_sync = round(h_screen - (1 - y - extent_y / 2) * h_screen / 2)
    return w_sync, h_sync


class Frame2TTL(SerialSingleton):
    def __init__(self, *args, **kwargs) -> None:
        # override default arguments of super-class
        if 'baudrate' not in kwargs:
            kwargs['baudrate'] = 115200
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 0.5
        if 'write_timeout' not in kwargs:
            kwargs['write_timeout'] = 0.5

        super().__init__(*args, **kwargs)
        self.flushInput()
        self.flushOutput()

        self._streaming = False
        self._calibration_timer = QtCore.QBasicTimer()

        # get more information on USB device
        port_info = next((p for p in comports() if p.device == self.portstr), None)
        if not port_info or not port_info.vid:
            raise OSError(f'Device on {self.portstr} is not a Frame2TTL')

        # detect SAMD21 Mini Breakout (Frame2TTL v1)
        is_samd21mini = port_info.vid == 0x1B4F and port_info.pid in [0x8D21, 0x0D21]
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

    def handshake(self, raise_on_fail: bool = False) -> bool:
        self.flushInput()
        self.write(b'C')
        status = self.read() == bytes([218])
        if not status and raise_on_fail:
            raise OSError(f'Device on {self.portstr} is not a Frame2TTL')
        return status

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
        return samples[0:n_samples]

    def calibration(
        self,
        color: tuple[int, int, int] = (0, 0, 0),
        screen: int | None = None,
        width: int = _convert_bonsai_sync_pos()[0],
        height: int = _convert_bonsai_sync_pos()[1],
        n_samples: int = 2000,
    ) -> np.array:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        win = _QtCalibrator(frame2ttl=self, color_rgb=color, width=width, height=height)
        app.exec_()
        return win.data


class _QtCalibrator(QDialog):
    data: np.array

    def __init__(
        self,
        frame2ttl: Frame2TTL,
        color_rgb: tuple[int, int, int] = (0, 0, 0),
        screen_index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        n_samples: int = 50,
        **kwargs,
    ):
        self.frame2ttl = frame2ttl
        self.n_samples = n_samples

        # try to detect screen_index, get screen dimensions
        if screen_index is None:
            for screen_index, screen in enumerate(QApplication.screens()):
                if screen.size().width() == 2048 and screen.size().height() == 1536:
                    break
            else:
                log.warning('Cannot identify iPad screen automatically. Defaulting to screen index 0.')
                screen_index = 0
                screen = QApplication.screens()[0]

        # display frameless QDialog with given color
        super().__init__(**kwargs)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAutoFillBackground(True)
        self.color_rgb = color_rgb
        self.setFixedSize(width, height)
        screen_geometry = QApplication.desktop().screenGeometry(screen_index)
        self.move(
            QPoint(screen_geometry.x() + screen_geometry.width() - width, screen_geometry.y() + screen_geometry.height() - height)
        )
        self.show()
        self.activateWindow()

        QtCore.QTimer.singleShot(100, self.measure)

    @property
    def color_rgb(self) -> tuple[int, int, int]:
        return self.palette().color(QtGui.QPalette.Window).getRgb()[:3]

    @color_rgb.setter
    def color_rgb(self, color: tuple[int, int, int]):
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor.fromRgb(*color))
        self.setPalette(palette)

    def measure(self) -> np.array:
        self.frame2ttl.flushInput()
        self.frame2ttl.streaming = True
        self.data = self.frame2ttl.sample(n_samples=self.n_samples)
        self.frame2ttl.streaming = False
        self.close()


a = Frame2TTL('COM11')
x = a.calibration(screen=1)
print(np.mean(x))
# print(_convert_bonsai_sync_pos())
