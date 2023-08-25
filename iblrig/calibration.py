from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import QPoint
from iblrig import path_helper
from iblrig.frame2TTL import frame2ttl_factory
from time import sleep
import sys


class Calibrator(QMainWindow):

    def __init__(self, screen: int = 0, size: int = 80, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFixedSize(size, size)
        (x, y, w, h) = QApplication.desktop().screenGeometry(screen).getRect()
        self.move(QPoint(x + w - size, y + h - size))
        self.show()

        hw_settings = path_helper.load_settings_yaml('hardware_settings.yaml')
        self.f2ttl = frame2ttl_factory(hw_settings["device_frame2ttl"]["COM_F2TTL"])

        self.state = 0
        self.timer = QtCore.QBasicTimer()
        self.timer.start(500, self)

    def timerEvent(self, event):
        if event.timerId() == self.timer.timerId():
            self._stateMachine()
        else:
            QtGui.QFrame.timerEvent(self, event)

    def _measure(self):
        pass

    def _stateMachine(self):
        print('hello')
        match self.state:
            case 0:
                self.setStyleSheet("QMainWindow {background: white};")
                self.update()
            case 1:
                self.timer.stop()
                self._measure()
                self.timer.start(500, self)
            case 2:
                self.setStyleSheet("QMainWindow {background: black};")
                self.update()
            case 3:
                self.timer.stop()
                self._measure()
                self.timer.start(200, self)
            case 4:
                self.timer.stop()
                (a, *b) = self.f2ttl.calc_recomend_thresholds()
                if a < 0:
                    print('Oh no!')
                else:
                    print(f'light: {a}, dark: {b[0]}')
                self.close()
        self.state += 1

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Calibrator(screen=1, size=100)
    # app.exec_()
    sys.exit(app.exec_())