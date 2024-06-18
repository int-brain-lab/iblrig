
from pathlib import Path

import pandas as pd
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QAbstractScrollArea, QHeaderView, QWidget

from iblrig.gui.tools import DataFrameTableModel, Worker
from iblrig.gui.ui_tab_data import Ui_TabData
from iblrig.path_helper import get_local_and_remote_paths


class TabData(QWidget, Ui_TabData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.localSubjectsDir = get_local_and_remote_paths().local_subjects_folder

        data = pd.DataFrame({'Subject': [], 'Date': [], 'Index': [], 'Task(s)': [], 'Status': []})
        data = pd.DataFrame(data)

        self.model = DataFrameTableModel(df=data)
        self.tableView.setModel(self.model)
        self.tableView.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

        header = self.tableView.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Column 0 will stretch
        for col in [0, 1, 2, 4]:
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tableView.setWordWrap(False)

        self.pushButtonUpdate.clicked.connect(self.updateData)

        self.updateData()

    def updateData(self):
        worker = Worker(self._updateData)
        worker.signals.result.connect(self._onUpdateDataResult)
        QThreadPool.globalInstance().start(worker)

    def _updateData(self) -> pd.DataFrame:
        rows = []
        dirs = Path(self.localSubjectsDir).glob('*/*/*/')
        for d in dirs:
            if not d.is_dir():
                continue
            idx = int(d.name)
            date = d.parents[0].name
            subject = d.parents[1].name
            rows += [pd.DataFrame({'Subject': [subject], 'Date': [date], 'Index': [idx], 'Task(s)': [None], 'Status': [None]})]
        return pd.concat(rows)

    def _onUpdateDataResult(self, result: pd.DataFrame):
        self.model.setDataFrame(result)
