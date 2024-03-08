import logging

from dateutil.utils import today
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets

from iblrig.frame2ttl import Frame2TTL
from iblrig.gui.tools import Worker
from iblrig.gui.ui_frame2ttl import Ui_frame2ttl
from iblrig.path_helper import save_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings

log = logging.getLogger(__name__)


class Frame2TTLCalibrationDialog(QtWidgets.QDialog, Ui_frame2ttl):
    def __init__(self, *args, hardware_settings: HardwareSettings, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.hardware_settings = hardware_settings
        self.frame2ttl = Frame2TTL(port=hardware_settings.device_frame2ttl.COM_F2TTL)
        self.target = Frame2TTLCalibrationTarget(self, color=QtGui.QColorConstants.White)
        self.light = None
        self.dark = None
        self._success = True

        self.uiLabelPortValue.setText(self.frame2ttl.portstr)
        self.uiLabelHardwareValue.setText(str(self.frame2ttl.hw_version))
        self.uiLabelFirmwareValue.setText(str(self.frame2ttl.fw_version))
        self.buttonBox.buttons()[0].setEnabled(False)
        self.show()

        # start worker for first calibration step: light condition
        worker = Worker(self.frame2ttl.calibrate, condition='light')
        worker.signals.result.connect(self._on_calibrate_light_result)
        QtCore.QThreadPool.globalInstance().tryStart(worker)
        self.uiLabelLightValue.setText('calibrating ...')

    def _on_calibrate_light_result(self, result: tuple[int, bool]):
        (self.light, self._success) = result
        self.uiLabelLightValue.setText(f'{self.light} {self.frame2ttl.unit_str}')

        # start worker for second calibration step: dark condition
        self.target.color = QtGui.QColorConstants.Black
        worker = Worker(self.frame2ttl.calibrate, condition='dark')
        worker.signals.result.connect(self._on_calibrate_dark_result)
        QtCore.QThreadPool.globalInstance().tryStart(worker)
        self.uiLabelDarkValue.setText('calibrating ...')

    def _on_calibrate_dark_result(self, result: tuple[int, bool]):
        (self.dark, self._success) = result
        self.uiLabelDarkValue.setText(f'{self.dark} {self.frame2ttl.unit_str}')

        if self._success:
            self.frame2ttl.set_thresholds(light=self.light, dark=self.dark)
            self.hardware_settings.device_frame2ttl.F2TTL_DARK_THRESH = self.dark
            self.hardware_settings.device_frame2ttl.F2TTL_LIGHT_THRESH = self.light
            self.hardware_settings.device_frame2ttl.F2TTL_CALIBRATION_DATE = today()
            save_pydantic_yaml(self.hardware_settings.hardware_settings)
            self.uiLabelResult.setText('Calibration successful.\nSettings have been updated.')
        else:
            self.uiLabelResult.setText('Calibration failed.\nVerify that sensor is placed correctly.')
        self.buttonBox.buttons()[0].setEnabled(True)
        self.frame2ttl.close()


class Frame2TTLCalibrationTarget(QtWidgets.QDialog):
    def __init__(
        self,
        parent,
        color: QtGui.QColor = QtGui.QColorConstants.White,
        screen_index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        rel_pos_x: float = 1.33,
        rel_pos_y: float = -1.03,
        rel_extent_x: float = 0.2,
        rel_extent_y: float = 0.2,
        **kwargs,
    ):
        # try to detect screen_index, get screen dimensions
        if screen_index is None:
            for screen_index, screen in enumerate(QtWidgets.QApplication.screens()):
                if screen.size().width() == 2048 and screen.size().height() == 1536:
                    break
            else:
                log.warning('Defaulting to screen index 0.')
                screen_index = 0
                screen = QtWidgets.QApplication.screens()[0]

        # convert relative parameters (used in bonsai scripts) to width and height
        if width is None and height is None:
            screen_width = screen.geometry().width()
            screen_height = screen.geometry().height()
            width = round(screen_width - (screen_width + (rel_pos_x - rel_extent_x / 2) * screen_height) / 2)
            height = round(screen_height - (1 - rel_pos_y - rel_extent_y / 2) * screen_height / 2)

        # display frameless QDialog with given color
        super().__init__(parent, **kwargs)
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Dialog)
        self.setAutoFillBackground(True)
        self._set_color(color)
        self.setFixedSize(width, height)
        screen_geometry = QtWidgets.QApplication.desktop().screenGeometry(screen_index)
        self.move(
            QtCore.QPoint(
                screen_geometry.x() + screen_geometry.width() - width, screen_geometry.y() + screen_geometry.height() - height
            )
        )
        self.show()
        QtTest.QTest.qWait(500)

    def _set_color(self, color: QtGui.QColor):
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)

    @property
    def color(self) -> QtGui.QColor:
        return self.palette().color(QtGui.QPalette.Window)

    @color.setter
    def color(self, color: QtGui.QColor):
        self._set_color(color)
        self.update()
        QtTest.QTest.qWait(500)
