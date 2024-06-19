from concurrent.futures import ThreadPoolExecutor
from os import path
from pathlib import Path

import pandas as pd
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QHeaderView, QWidget

from iblrig.gui.tools import DataFrameTableModel, Worker
from iblrig.gui.ui_tab_data import Ui_TabData
from iblrig.path_helper import get_local_and_remote_paths


class TabData(QWidget, Ui_TabData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.localSubjectsDir = get_local_and_remote_paths().local_subjects_folder

        self._columns = ['Subject', 'Date', 'Index', 'Task(s)', 'Status']
        data = pd.DataFrame(None, index=[], columns=self._columns)
        self.model = DataFrameTableModel(df=data)
        self.tableView.setModel(self.model)

        header = self.tableView.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Column 0 will stretch
        for col in [0, 1, 2, 4]:
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.pushButtonUpdate.clicked.connect(self.updateData)

        # self.updateData()

    def updateData(self):
        worker = Worker(self._updateData)
        worker.signals.result.connect(self._onUpdateDataResult)
        QThreadPool.globalInstance().start(worker)

    def _updateData(self) -> pd.DataFrame:
        dirs = [str(d) for d in Path(self.localSubjectsDir).glob('*/*/[0-9][0-9][0-9]/') if d.is_dir()]
        data = []

        def process_directory(dir_path):
            idx = int(path.basename(dir_path))
            date = path.basename(path.dirname(dir_path))
            subject = path.basename(path.dirname(path.dirname(dir_path)))
            return {'Subject': subject, 'Date': date, 'Index': idx, 'Task(s)': None, 'Status': None}

        with ThreadPoolExecutor() as executor:
            for result in executor.map(process_directory, dirs):
                data.append(result)
        return pd.DataFrame(data)

    def _onUpdateDataResult(self, result: pd.DataFrame):
        self.model.setDataFrame(result)
