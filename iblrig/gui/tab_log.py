from qtpy.QtCore import QSettings, Qt, QTimer, Signal, Slot
from qtpy.QtGui import QBrush, QColorConstants, QFont, QIcon
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from iblrig.gui import resources_rc  # noqa: F401


class TabLog(QWidget):
    _narrative = b''
    narrativeUpdated = Signal(bytes)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = QSettings()

        # splitter widget
        splitter = QSplitter(Qt.Vertical, self)
        splitter.setFrameShape(QFrame.NoFrame)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)

        # upper group box (log)
        group_box_log = QGroupBox('Session Log', splitter)
        size_policy_log = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        size_policy_log.setVerticalStretch(3)
        group_box_log.setSizePolicy(size_policy_log)
        group_box_log.setMinimumHeight(200)

        # lower group box (session narrative)
        group_box_narrative = QGroupBox('Session Narrative', splitter)
        size_policy_narrative = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        size_policy_narrative.setVerticalStretch(1)
        group_box_narrative.setSizePolicy(size_policy_narrative)

        # read-only edit field for log
        self.plainTextEditLog = QPlainTextEdit(group_box_log)
        self.plainTextEditLog.setStyleSheet('QPlainTextEdit {background-color: rgb(0, 0, 0)};')
        self.plainTextEditLog.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.plainTextEditLog.setReadOnly(True)
        font = QFont('Monospace')
        font.setStyleHint(QFont.TypeWriter)
        self.plainTextEditLog.setFont(font)

        # toolbar for upper group box
        toolbar_widget = QWidget(group_box_log)
        spin_box_font_size = QSpinBox(toolbar_widget)
        spin_box_font_size.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        spin_box_font_size.setButtonSymbols(QAbstractSpinBox.PlusMinus)
        spin_box_font_size.setAccelerated(False)
        spin_box_font_size.setMinimum(7)
        spin_box_font_size.setMaximum(99)
        spin_box_font_size.setProperty('value', 11)
        spin_box_font_size.valueChanged.connect(self._set_font_size)
        spin_box_font_size.setValue(self.settings.value('font_size', 11, int))
        spin_box_font_size.setToolTip("Set the log's font size")
        label_font_size = QLabel('&Font Size', toolbar_widget)
        label_font_size.setToolTip("Set the log's font size")
        label_font_size.setBuddy(spin_box_font_size)
        self.button_clipboard = QPushButton(' &Copy', toolbar_widget)
        self.button_clipboard.setIcon(QIcon(':/images/clipboard'))
        self.button_clipboard.setToolTip('Copy log to clipboard')
        self.button_clipboard.setEnabled(False)
        self.button_clipboard.clicked.connect(self._copy_to_clipboard)

        # edit field for narrative
        self.plainTextEditNarrative = QPlainTextEdit(group_box_narrative)
        self.plainTextEditNarrative.setPlaceholderText('Enter your obvservations here ...')
        self.plainTextEditNarrative.textChanged.connect(self._narrative_changed)
        self.plainTextEditNarrative.setStyleSheet('QPlainTextEdit {background-color: rgb(0, 0, 0)};')

        # assemble layouts and widgets
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)
        layout_log = QVBoxLayout(group_box_log)
        layout_log.addWidget(self.plainTextEditLog)
        layout_log.addWidget(toolbar_widget)
        layout_toolbar = QHBoxLayout(toolbar_widget)
        layout_toolbar.setContentsMargins(0, 0, 0, 0)
        layout_toolbar.addWidget(label_font_size)
        layout_toolbar.addWidget(spin_box_font_size)
        layout_toolbar.addStretch(1)
        layout_toolbar.addWidget(self.button_clipboard)
        layout_narrative = QVBoxLayout(group_box_narrative)
        layout_narrative.addWidget(self.plainTextEditNarrative)
        layout_splitter = QVBoxLayout(splitter)
        layout_splitter.setContentsMargins(0, 0, 0, 0)
        layout_splitter.addWidget(group_box_log)
        layout_splitter.addWidget(group_box_narrative)

        # timer
        self.narrativeTimer = QTimer(self)
        self.narrativeTimer.setSingleShot(True)
        self.narrativeTimer.timeout.connect(self.narrativeTimerTimeout)

    @Slot()
    def _narrative_changed(self):
        self.narrativeTimer.start(5000)

    @Slot()
    def narrativeTimerTimeout(self):
        narrative = str.encode(self.plainTextEditNarrative.toPlainText())
        if narrative != self._narrative:
            self.narrativeUpdated.emit(narrative)
            self._narrative = narrative

    @Slot()
    def clear(self):
        """Clear the log."""
        self.button_clipboard.setEnabled(False)
        self.plainTextEditLog.clear()

    @Slot(str, str)
    def appendText(self, text: str, color: str = 'White'):
        """
        Append text to the log.

        Parameters
        ----------
        text : str
            The text to append.
        color : str, optional
            The color of the text. Should be a valid color name recognized by
            QColorConstants. Defaults to 'White'.
        """
        self.button_clipboard.setEnabled(True)
        self._set_log_color(color)
        self.plainTextEditLog.appendPlainText(text)

    @Slot()
    def _copy_to_clipboard(self):
        """Copy the log contents to the clipboard as a markdown code-block."""
        text = f'"""\n{self.plainTextEditLog.toPlainText()}\n"""'
        QApplication.clipboard().setText(text)

    @Slot(int)
    def _set_font_size(self, font_size: int):
        """
        Set the font size of the log-widget's contents.

        Parameters
        ----------
        font_size : int
            Font size of the log-widget's contents in points.
        """
        font = self.plainTextEditLog.font()
        font.setPointSize(font_size)
        self.plainTextEditLog.setFont(font)
        self.settings.setValue('font_size', font_size)

    def _set_log_color(self, color_name: str):
        """
        Set the foreground color of characters in the log widget.

        Parameters
        ----------
        color_name : str, optional
            The name of the color to set. Default is 'White'. Should be a valid color name
            recognized by QColorConstants. If the provided color name is not found,
            it defaults to QColorConstants.White.
        """
        color = getattr(QColorConstants, color_name, QColorConstants.White)
        char_format = self.plainTextEditLog.currentCharFormat()
        char_format.setForeground(QBrush(color))
        self.plainTextEditLog.setCurrentCharFormat(char_format)
