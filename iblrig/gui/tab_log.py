from PyQt5.QtCore import QSettings, pyqtSlot
from PyQt5.QtGui import QBrush, QColorConstants, QFont
from PyQt5.QtWidgets import QApplication, QWidget

from iblrig.gui.ui_tab_log import Ui_TabLog


class TabLog(QWidget, Ui_TabLog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.settings = QSettings()

        font = QFont('Monospace')
        font.setStyleHint(QFont.TypeWriter)
        self.plainTextEditLog.setFont(font)

        self.pushButtonClipboard.setEnabled(False)
        self.pushButtonClipboard.clicked.connect(self._copy_to_clipboard)

        self.spinBoxFontSize.valueChanged.connect(self._set_font_size)
        self.spinBoxFontSize.setValue(self.settings.value('font_size', 11, int))

    @pyqtSlot()
    def clear(self):
        self.pushButtonClipboard.setEnabled(False)
        self.plainTextEditLog.clear()

    @pyqtSlot(str, str)
    def append_text(self, text: str, color: str = 'White'):
        self.pushButtonClipboard.setEnabled(True)
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
        """Copies the log contents to the clipboard (as a markdown code-block)"""
        text = f'"""\n{self.plainTextEditLog.toPlainText()}\n"""'
        QApplication.clipboard().setText(text)

    @pyqtSlot(int)
    def _set_font_size(self, value: int):
        font = self.plainTextEditLog.font()
        font.setPointSize(value)
        self.plainTextEditLog.setFont(font)
        self.settings.setValue('font_size', value)
