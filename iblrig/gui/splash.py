from qtpy.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QSize, Qt, QThreadPool, QTimer
from qtpy.QtGui import QFont, QPalette, QPixmap, QRadialGradient
from qtpy.QtWidgets import QDialog, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from typing_extensions import override

from iblqt.core import Worker
from iblrig import __version__ as version
from iblrig.constants import COPYRIGHT_YEAR
from iblrig.hardware_validation import Result, get_all_validators
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings


class Splash(QDialog):
    validation_results: list[Result] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hardware_settings = load_pydantic_yaml(HardwareSettings)
        self.rig_settings = load_pydantic_yaml(RigSettings)

        # window properties
        self.setWindowModality(Qt.ApplicationModal)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.setMinimumSize(QSize(350, 400))
        self.setMaximumSize(QSize(350, 400))
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.installEventFilter(self)

        # background gradient
        gradient = QRadialGradient(0.5, 0.45, 0.5, 0.5, 0.45)
        gradient.setColorAt(0.0, QPalette().window().color().lighter(110))
        gradient.setColorAt(1.0, QPalette().window().color().darker(115))
        gradient.setCoordinateMode(gradient.ObjectMode)
        p = QPalette()
        p.setBrush(QPalette.Window, gradient)
        self.setPalette(p)

        # logo
        horizontal_widget = QWidget(self)
        widget_logo = QWidget(horizontal_widget)
        widget_logo.setMinimumSize(QSize(250, 240))
        widget_logo.setMaximumSize(QSize(250, 16777215))
        logo = QLabel(widget_logo)
        logo.setGeometry(50, 100, 150, 150)
        logo.setPixmap(QPixmap(':/images/logo_ibl'))
        logo.setScaledContents(True)
        hat = QLabel(widget_logo)
        hat.setGeometry(0, 50, 150, 150)
        hat.setPixmap(QPixmap(':/images/iblrig_logo'))
        hat.setScaledContents(True)

        # text labels
        label_rig = QLabel('IBLRIG Wizard', self)
        label_rig.setFont(QFont('Arial', 15, 75, False))
        label_rig.setAlignment(Qt.AlignCenter)
        label_version = QLabel(f'v{version}', self)
        label_version.setAlignment(Qt.AlignCenter)
        label_copyright = QLabel(f'© {COPYRIGHT_YEAR}, International Brain Laboratory', self)
        label_copyright.setAlignment(Qt.AlignCenter)

        # system validation status
        widget_status = QWidget(self)
        widget_status.setAutoFillBackground(False)
        widget_status.setStyleSheet('background-color: rgb(255, 255, 255);')
        layout_status = QHBoxLayout(widget_status)
        layout_status.setContentsMargins(9, 2, 9, 2)
        self.label_status = QLabel(widget_status)
        layout_status.addWidget(self.label_status)

        # layout
        horizontal_layout = QHBoxLayout(horizontal_widget)
        horizontal_layout.addStretch(1)
        horizontal_layout.addWidget(widget_logo)
        horizontal_layout.addStretch(1)
        vertical_layout = QVBoxLayout(self)
        vertical_layout.setContentsMargins(0, 0, 0, 0)
        vertical_layout.setSpacing(0)
        vertical_layout.addWidget(horizontal_widget)
        vertical_layout.addSpacing(30)
        vertical_layout.addWidget(label_rig)
        vertical_layout.addWidget(label_version)
        vertical_layout.addStretch(40)
        vertical_layout.addWidget(widget_status)
        vertical_layout.addSpacing(20)
        vertical_layout.addWidget(label_copyright)
        vertical_layout.addSpacing(5)
        self.setLayout(vertical_layout)

        # start validation worker
        worker = Worker(self.validation)
        worker.signals.finished.connect(self.close)
        QThreadPool.globalInstance().tryStart(worker)
        QTimer.singleShot(20000, self.close)  # max wait time

        # extremely important animation
        hat.setProperty('pos', QPoint(0, -250))
        self.animation = QPropertyAnimation(hat, b'pos')
        self.animation.setEasingCurve(QEasingCurve.InQuad)
        self.animation.setEndValue(QPoint(0, 40))
        self.animation.setDuration(500)

        self.show()
        self.animation.start()

    def validation(self):
        for validator in get_all_validators():
            validator_instance = validator(hardware_settings=self.hardware_settings, iblrig_settings=self.rig_settings)
            self.label_status.setText(f'Validating {validator_instance.name} ...')
            for result in validator_instance.run():
                self.validation_results.append(result)

    @override
    def eventFilter(self, obj, event):
        """Disregard all key-presses."""
        return obj is self and event.type() == QEvent.KeyPress
