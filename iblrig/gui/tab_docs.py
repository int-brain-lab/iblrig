import webbrowser

from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWidgets import QWidget
from typing_extensions import override

from iblrig.constants import URL_DOC
from iblrig.gui.ui_tab_docs import Ui_TabDocs


class TabDocs(QWidget, Ui_TabDocs):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # connect signals to slots
        self.uiPushWebHome.clicked.connect(lambda: self.webEngineView.load(QUrl(URL_DOC)))
        self.uiPushWebBack.clicked.connect(lambda: self.webEngineView.back())
        self.uiPushWebForward.clicked.connect(lambda: self.webEngineView.forward())
        self.uiPushWebBrowser.clicked.connect(lambda: webbrowser.open(str(self.webEngineView.url().url())))
        self.webEngineView.urlChanged.connect(self._on_doc_url_changed)

        # initialize webEngineView
        self.webEngineView.setPage(CustomWebEnginePage(self))
        self.webEngineView.setUrl(QUrl(URL_DOC))

    def _on_doc_url_changed(self):
        self.uiPushWebBack.setEnabled(len(self.webEngineView.history().backItems(1)) > 0)
        self.uiPushWebForward.setEnabled(len(self.webEngineView.history().forwardItems(1)) > 0)


class CustomWebEnginePage(QWebEnginePage):
    """
    Custom implementation of QWebEnginePage to handle navigation requests.

    This class overrides the acceptNavigationRequest method to handle link clicks.
    If the navigation type is a link click and the clicked URL does not start with
    a specific prefix (URL_DOC), it opens the URL in the default web browser.
    Otherwise, it delegates the handling to the base class.

    Adapted from: https://www.pythonguis.com/faq/qwebengineview-open-links-new-window/
    """

    @override
    def acceptNavigationRequest(self, url: QUrl, navigation_type: QWebEnginePage.NavigationType, is_main_frame: bool):
        """
        Decide whether to allow or block a navigation request.

        Parameters
        ----------
        url : QUrl
            The URL being navigated to.

        navigation_type : QWebEnginePage.NavigationType
            The type of navigation request.

        is_main_frame : bool
            Indicates whether the request is for the main frame.

        Returns
        -------
        bool
            True if the navigation request is accepted, False otherwise.
        """
        if navigation_type == QWebEnginePage.NavigationTypeLinkClicked and not url.url().startswith(URL_DOC):
            webbrowser.open(url.url())
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)
