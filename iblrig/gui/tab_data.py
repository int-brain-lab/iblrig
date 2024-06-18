from PyQt5.QtWidgets import QWidget

from iblrig.gui.ui_tab_data import Ui_TabData


class TabData(QWidget, Ui_TabData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
