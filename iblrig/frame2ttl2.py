import logging
import struct
import time

import numpy as np
from matplotlib import pyplot as plt
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
    def __init__(self, port: str, **kwargs) -> None:
        # identify micro-controller
        port_info = next((p for p in comports() if p.device == port), None)
        is_samd21mini = port_info.vid == 0x1B4F and port_info.pid in [0x8D21, 0x0D21]
        is_teensy = port_info.vid == 0x16C0 and port_info.pid == 0x0483
        if not is_samd21mini and not is_teensy:
            raise OSError(f'Device on {port} is not a Frame2TTL')

        # override default arguments of super-class
        if 'baudrate' not in kwargs:
            kwargs['baudrate'] = 115200
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 0.5
        if 'write_timeout' not in kwargs:
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

        # initialize members
        self._dark_threshold = None
        self._light_threshold = None
        self._streaming = False
        match self.hw_version:
            case 1:
                self._unit_str = 'μs'
                self._dtype_sensorval = np.uint32
                self._dtype_streaming = np.uint32
                self._dtype_threshold = np.int16
            case _:
                self._unit_str = 'bits/ms'
                self._dtype_rawsensor = np.uint16
                self._dtype_streaming = np.uint16
                self._dtype_threshold = np.int16

        # log status
        log.debug(f'Connected to Frame2TTL v{self.hw_version} on port {self.portstr}. ' f'Firmware Version: {self.fw_version}.')

    @property
    def streaming(self) -> bool:
        return self._streaming

    @streaming.setter
    def streaming(self, state: bool):
        self.write(struct.pack('<c?', b'S', state))
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
        buffer = bytearray(n_samples * self._dtype_streaming().itemsize)
        original_timeout = self.timeout
        self.timeout = None
        self.streaming = True
        self.readinto(buffer)
        self.streaming = False
        self.timeout = original_timeout
        return np.frombuffer(buffer, dtype=self._dtype_streaming)

    def calibration(self, n_samples: int = 500):
        dark = self.calibrate_single_color(color_rgb=(0, 0, 0), n_samples=n_samples)
        light = self.calibrate_single_color(color_rgb=(255, 255, 255), n_samples=n_samples)
        print(len(light))
        thresh_dark = int(np.floor(np.min(dark)))
        thresh_light = int(np.ceil(np.max(light)))
        self.set_thresholds(thresh_dark, thresh_light)
        self.plot_calibration(dark_vals=dark, light_vals=light, dark_thresh=thresh_dark, light_thresh=thresh_light)

    def plot_calibration(self, dark_vals: np.ndarray[int], light_vals: np.ndarray[int], dark_thresh: int, light_thresh: int):
        plt.hist(dark_vals, orientation='horizontal', fc='black', ec='black', histtype='step', fill=True)
        plt.hist(light_vals, orientation='horizontal', fc='white', ec='white', histtype='step', fill=True)
        plt.axhline(light_thresh, color='red', ls='--')
        plt.axhline(dark_thresh, color='red', ls='--')
        x_center = np.mean(plt.gca().get_xlim())
        y_extent = np.diff(plt.gca().get_ylim())
        plt.text(x_center, light_thresh + y_extent / 100, f'Light Threshold: {light_thresh:.0f}', ha='center', va='top')
        plt.text(x_center, dark_thresh - y_extent / 100, f'Dark Threshold: {dark_thresh:.0f}', ha='center', va='bottom')
        plt.gca().invert_yaxis()
        plt.gca().get_xaxis().set_visible(False)
        plt.gca().set_facecolor((0.5, 0.5, 0.5))
        plt.xlabel('Count')
        plt.ylabel(f'Brightness Readings [{self._unit_str}]')
        plt.title('Frame2TTL Calibration')
        plt.show()

    def set_thresholds(self, dark: int, light: int):
        self.write(struct.pack('<cHH' if self.hw_version == 1 else '<chh', b'T', dark, light))
        self._dark_threshold = dark
        self._light_threshold = light

    def get_thresholds(self) -> tuple[int, int]:
        pass

    @property
    def dark_threshold(self) -> int:
        return self._dark_threshold

    @dark_threshold.setter
    def dark_threshold(self, value: int):
        self.set_thresholds(dark=value, light=self._light_threshold)

    @property
    def light_threshold(self) -> int:
        return self._dark_threshold

    @light_threshold.setter
    def light_threshold(self, value: int):
        self.set_thresholds(dark=self._dark_threshold, light=value)

    def calibrate_single_color(
        self,
        color_rgb: tuple[int, int, int] = (0, 0, 0),
        screen_index: int | None = None,
        width: int = _convert_bonsai_sync_pos()[0],
        height: int = _convert_bonsai_sync_pos()[1],
        n_samples: int = 2000,
    ) -> np.array:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        win = _QtCalibrator(
            frame2ttl=self, color_rgb=color_rgb, screen_index=screen_index, width=width, height=height, n_samples=n_samples
        )
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
        n_samples: int = 1000,
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

        QtCore.QTimer.singleShot(500, self.measure)

    @property
    def color_rgb(self) -> tuple[int, int, int]:
        return self.palette().color(QtGui.QPalette.Window).getRgb()[:3]

    @color_rgb.setter
    def color_rgb(self, color: tuple[int, int, int]):
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor.fromRgb(*color))
        self.setPalette(palette)

    def measure(self) -> np.array:
        self.data = self.frame2ttl.sample(n_samples=self.n_samples)
        self.close()


Frame2TTL('COM11').calibration()
