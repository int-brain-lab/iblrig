import webbrowser

from qtpy.QtCore import QUrl
from qtpy.QtWebEngineWidgets import QWebEnginePage
from typing_extensions import override

from iblqt.widgets import RestrictedWebView
from iblrig.constants import URL_DOC


class TabDocs(RestrictedWebView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)


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
    def acceptNavigationRequest(self, url: QUrl, navigationType: QWebEnginePage.NavigationType, is_main_frame: bool):
        """
        Decide whether to allow or block a navigation request.

        Parameters
        ----------
        url : QUrl
            The URL being navigated to.

        navigationType : QWebEnginePage.NavigationType
            The type of navigation request.

        is_main_frame : bool
            Indicates whether the request is for the main frame.

        Returns
        -------
        bool
            True if the navigation request is accepted, False otherwise.
        """
        if navigationType == QWebEnginePage.NavigationTypeLinkClicked and not url.url().startswith(URL_DOC):
            webbrowser.open(url.url())
            return False
        return super().acceptNavigationRequest(url, navigationType, is_main_frame)
