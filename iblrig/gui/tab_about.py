import webbrowser

from qtpy.QtCore import QSize, Qt, QThreadPool
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtWidgets import QCommandLinkButton, QGridLayout, QLabel, QSizePolicy, QSpacerItem, QWidget

from iblqt.core import Worker
from iblrig import __version__ as iblrig_version
from iblrig.constants import COPYRIGHT_YEAR, URL_DISCUSSION, URL_DOC, URL_ISSUES, URL_REPO
from iblrig.tools import get_anydesk_id


class TabAbout(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # spacer items
        horizontal_spacer_1 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        horizontal_spacer_2 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        horizontal_spacer_3 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        horizontal_spacer_4 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # logo
        label_logo = QLabel('', self)
        label_logo.setMaximumSize(QSize(90, 90))
        label_logo.setPixmap(QPixmap(':/images/iblrig_logo'))
        label_logo.setScaledContents(True)

        # copyright label
        label_copyright = QLabel(f'**IBLRIG v{iblrig_version}**\n\n© {COPYRIGHT_YEAR}, International Brain Laboratory', self)
        label_copyright.setTextFormat(Qt.MarkdownText)
        label_copyright.setAlignment(Qt.AlignCenter)

        # command link buttons
        button_github = QCommandLinkButton('&GitHub', self)
        button_github.setIcon(QIcon(':/images/github'))
        button_github.setToolTip('Open the IBLRIG GitHub repository')
        button_github.clicked.connect(lambda: webbrowser.open(URL_REPO))
        button_doc = QCommandLinkButton('&Documentation', self)
        button_doc.setIcon(QIcon(':/images/help'))
        button_doc.setToolTip('Open the IBLRIG documentation')
        button_doc.clicked.connect(lambda: webbrowser.open(URL_DOC))
        button_discussion = QCommandLinkButton('Discussion &Board', self)
        button_discussion.setIcon(QIcon(':/images/discussion'))
        button_discussion.setToolTip('Open the IBLRIG discussion board')
        button_discussion.clicked.connect(lambda: webbrowser.open(URL_DISCUSSION))
        button_issues = QCommandLinkButton('&Issue Tracker', self)
        button_issues.setIcon(QIcon(':/images/bug'))
        button_issues.setToolTip('Open the IBLRIG issue tracker')
        button_issues.clicked.connect(lambda: webbrowser.open(URL_ISSUES))

        # anydesk label
        self.label_anydesk = QLabel('', self)
        self.label_anydesk.setAlignment(Qt.AlignCenter)
        worker = Worker(get_anydesk_id, silent=True)
        worker.signals.result.connect(self._on_get_anydesk_result)
        QThreadPool.globalInstance().tryStart(worker)

        # grid layout
        grid_layout = QGridLayout(self)
        grid_layout.setRowStretch(0, 3)
        grid_layout.addItem(horizontal_spacer_1, 1, 0, 1, 2)
        grid_layout.addWidget(label_logo, 1, 2, 1, 1)
        grid_layout.addItem(horizontal_spacer_2, 1, 3, 1, 2)
        grid_layout.addWidget(label_copyright, 2, 0, 1, 5)
        grid_layout.setRowStretch(3, 3)
        grid_layout.addItem(horizontal_spacer_3, 4, 0, 4, 1)
        grid_layout.addWidget(button_github, 4, 1, 1, 3)
        grid_layout.addWidget(button_doc, 5, 1, 1, 3)
        grid_layout.addWidget(button_discussion, 6, 1, 1, 3)
        grid_layout.addWidget(button_issues, 7, 1, 1, 3)
        grid_layout.addItem(horizontal_spacer_4, 4, 4, 4, 1)
        grid_layout.setRowStretch(8, 4)
        grid_layout.addWidget(self.label_anydesk, 9, 0, 1, 5)

    def _on_get_anydesk_result(self, result: str | None) -> None:
        if result is not None:
            self.label_anydesk.setText(f'Your AnyDesk ID: {result}')
