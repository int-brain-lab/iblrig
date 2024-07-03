import webbrowser

from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QWidget

from iblrig import __version__ as iblrig_version
from iblrig.constants import COPYRIGHT_YEAR, URL_DISCUSSION, URL_DOC, URL_ISSUES, URL_REPO
from iblrig.gui.tools import Worker
from iblrig.gui.ui_tab_about import Ui_TabAbout
from iblrig.tools import get_anydesk_id


class TabAbout(QWidget, Ui_TabAbout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # set version & copyright strings
        self.uiLabelCopyright.setText(f'**IBLRIG v{iblrig_version}**\n\n© {COPYRIGHT_YEAR}, International Brain Laboratory')

        # define actions for command link buttons
        self.commandLinkButtonGitHub.clicked.connect(lambda: webbrowser.open(URL_REPO))
        self.commandLinkButtonDoc.clicked.connect(lambda: webbrowser.open(URL_DOC))
        self.commandLinkButtonIssues.clicked.connect(lambda: webbrowser.open(URL_ISSUES))
        self.commandLinkButtonDiscussion.clicked.connect(lambda: webbrowser.open(URL_DISCUSSION))

        # try to obtain AnyDesk ID
        worker = Worker(get_anydesk_id, silent=True)
        worker.signals.result.connect(self.onGetAnydeskResult)
        QThreadPool.globalInstance().tryStart(worker)

    def onGetAnydeskResult(self, result: str | None) -> None:
        if result is not None:
            self.uiLabelAnyDesk.setText(f'Your AnyDesk ID: {result}')
