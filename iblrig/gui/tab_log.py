from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QBrush, QColorConstants, QFont
from PyQt5.QtWidgets import QApplication, QWidget

from iblrig.gui.ui_tab_log import Ui_TabLog


class TabLog(QWidget, Ui_TabLog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        font = QFont('Monospace')
        font.setStyleHint(QFont.TypeWriter)
        font.setPointSize(9)
        self.plainTextEditLog.setFont(font)

        self.pushButtonClipboard.clicked.connect(self._copy_to_clipboard)

    @pyqtSlot()
    def clear(self):
        self.plainTextEditLog.clear()

    @pyqtSlot(str, str)
    def append_text(self, text: str, color: str = 'White'):
        self.set_log_color(color)
        self.plainTextEditLog.appendPlainText(text)

    def set_log_color(self, color: str):
        """
        Set the foreground color of characters in the log widget.

        Parameters
        ----------
        color : str, optional
            The name of the color to set. Default is 'White'. Should be a valid color name
            recognized by QtGui.QColorConstants. If the provided color name is not found,
            it defaults to QtGui.QColorConstants.White.
        """
        color = getattr(QColorConstants, color, QColorConstants.White)
        char_format = self.plainTextEditLog.currentCharFormat()
        char_format.setForeground(QBrush(color))
        self.plainTextEditLog.setCurrentCharFormat(char_format)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.plainTextEditLog.toPlainText())
