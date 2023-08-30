from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import QPoint
from iblrig.frame2ttl2 import Frame2TTL
import sys


class Calibrator(QDialog):

    def __init__(self, frame2ttl: Frame2TTL, screen: int = 0, size: int = 80, *args, **kwargs):
        self.data = None
        self.f2ttl = frame2ttl

        super().__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFixedSize(size, size)
        x, y, w, h = QApplication.desktop().screenGeometry(screen).getRect()
        self.move(QPoint(x + w - size, y + h - size))
        self.setStyleSheet("background: black")
        self.show()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.measure)
        self.timer.start(200)

    def measure(self):
        self.data = self.f2ttl.sample(10000)
        self.close()


if __name__ == '__main__':
    f2ttl = Frame2TTL('COM6')
    app = QApplication(sys.argv)
    win = Calibrator(frame2ttl=f2ttl, screen=1, size=100)
    app.exec_()
    print(win.data)
    f2ttl.close()
    sys.exit()
