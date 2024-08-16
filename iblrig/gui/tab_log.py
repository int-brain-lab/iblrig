from PyQt5.QtCore import QSettings, pyqtSlot
from PyQt5.QtGui import QBrush, QColorConstants, QFont
from PyQt5.QtWidgets import QApplication, QWidget

from iblrig.gui.ui_tab_log import Ui_TabLog


class TabLog(QWidget, Ui_TabLog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.settings = QSettings()

        font = QFont('Monospace')
        font.setStyleHint(QFont.TypeWriter)
        self.plainTextEditLog.setFont(font)

        self.pushButtonClipboard.setEnabled(False)
        self.pushButtonClipboard.clicked.connect(self.copyToClipboard)

        self.spinBoxFontSize.valueChanged.connect(self.setFontSize)
        self.spinBoxFontSize.setValue(self.settings.value('font_size', 11, int))

    @pyqtSlot()
    def clear(self):
        """Clear the log."""
        self.pushButtonClipboard.setEnabled(False)
        self.plainTextEditLog.clear()

    @pyqtSlot(str, str)
    def appendText(self, text: str, color: str = 'White'):
        """
        Append text to the log.

        Parameters
        ----------
        text : str
            The text to append.
        color : str, optional
            The color of the text. Should be a valid color name recognized by
            QtGui.QColorConstants. Defaults to 'White'.
        """
        self.pushButtonClipboard.setEnabled(True)
        self.setLogColor(color)
        self.plainTextEditLog.appendPlainText(text)

    @pyqtSlot()
    def copyToClipboard(self):
        """Copy the log contents to the clipboard as a markdown code-block."""
        text = f'"""\n{self.plainTextEditLog.toPlainText()}\n"""'
        QApplication.clipboard().setText(text)

    @pyqtSlot(int)
    def setFontSize(self, fontSize: int):
        """
        Set the font size of the log-widget's contents.

        Parameters
        ----------
        fontSize : int
            Font size of the log-widget's contents in points.
        """
        font = self.plainTextEditLog.font()
        font.setPointSize(fontSize)
        self.plainTextEditLog.setFont(font)
        self.settings.setValue('font_size', fontSize)

    def setLogColor(self, colorName: str):
        """
        Set the foreground color of characters in the log widget.

        Parameters
        ----------
        colorName : str, optional
            The name of the color to set. Default is 'White'. Should be a valid color name
            recognized by QtGui.QColorConstants. If the provided color name is not found,
            it defaults to QtGui.QColorConstants.White.
        """
        color = getattr(QColorConstants, colorName, QColorConstants.White)
        char_format = self.plainTextEditLog.currentCharFormat()
        char_format.setForeground(QBrush(color))
        self.plainTextEditLog.setCurrentCharFormat(char_format)
