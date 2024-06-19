import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from os import startfile

import pandas as pd
from PyQt5.QtCore import QModelIndex, Qt, QThreadPool
from PyQt5.QtWidgets import QHeaderView, QStyledItemDelegate, QWidget

from iblrig.gui.tools import DataFrameTableModel, Worker
from iblrig.gui.ui_tab_data import Ui_TabData
from iblrig.path_helper import get_local_and_remote_paths
from iblrig.transfer_experiments import CopyState, SessionCopier
from iblutil.util import dir_size

COPY_STATE_STRINGS = {
    CopyState.HARD_RESET: 'Hard Reset',
    CopyState.NOT_REGISTERED: 'Not Registered',
    CopyState.PENDING: 'Copy Pending',
    CopyState.COMPLETE: 'Copy Complete',
    CopyState.FINALIZED: 'Copy Finalized',
}


@dataclass
class Column:
    name: str
    hidden: bool = False
    resizeMode: QHeaderView.ResizeMode = QHeaderView.ResizeToContents


class DataItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        header_text = index.model().headerData(index.column(), Qt.Horizontal, Qt.DisplayRole)
        if 'Size' in header_text:
            option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter


class TabData(QWidget, Ui_TabData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self._localSubjectsPath = get_local_and_remote_paths().local_subjects_folder

        # define columns
        self._columns = [
            Column(name='Directory', hidden=True),
            Column(name='Date'),
            Column(name='Subject'),
            Column(name='Size / MB'),
            Column(name='Copy Status', resizeMode=QHeaderView.Stretch),
        ]

        # create empty model and view
        data = pd.DataFrame(None, index=[], columns=[c.name for c in self._columns])
        self.tableModel = DataFrameTableModel(df=data)
        self.tableView.setModel(self.tableModel)

        # set properties of columns in view
        for idx, column in enumerate(self._columns):
            self.tableView.setColumnHidden(idx, column.hidden)
            if not column.hidden:
                self.tableView.horizontalHeader().setSectionResizeMode(idx, column.resizeMode)
        self.tableView.setItemDelegate(DataItemDelegate(self.tableView))

        # connect signals to slots
        self.tableView.doubleClicked.connect(self._openDir)
        self.pushButtonUpdate.clicked.connect(self.updateData)

    def showEvent(self, a0):
        if len(self.tableModel.dataFrame) == 0:
            self.updateData()

    def updateData(self):
        worker = Worker(self._updateData)
        worker.signals.result.connect(self._onUpdateDataResult)
        QThreadPool.globalInstance().start(worker)

    def _updateData(self):
        data = []
        for session_dir in (d for d in self._localSubjectsPath.glob('*/????-??-??/[0-9][0-9][0-9]/') if d.is_dir()):
            copy_state = SessionCopier(session_dir).state
            copy_state_string = COPY_STATE_STRINGS.get(copy_state, 'N/A')

            # try to get folder creation time (cross-check with date-string of directory)
            date = datetime.strptime(session_dir.parent.name, '%Y-%m-%d')
            ctime = datetime.fromtimestamp(session_dir.stat().st_ctime)
            date = ctime if ctime.date() == date.date() else date
            date_string = date.strftime('%Y-%m-%d %H:%M:%S')

            # get size
            size_mb = round(dir_size(session_dir) / 1024**2 * 10) / 10

            subject = session_dir.parents[1].name
            data.append(
                {
                    'Directory': session_dir,
                    'Subject': subject,
                    'Date': date_string,
                    'Size / MB': size_mb,
                    'Copy Status': copy_state_string,
                }
            )
        return pd.DataFrame(data)

    def _onUpdateDataResult(self, data: pd.DataFrame):
        self.tableModel.setDataFrame(data)
        header = self.tableView.horizontalHeader()
        self.tableModel.sort(column=header.sortIndicatorSection(), order=header.sortIndicatorOrder())

    def _openDir(self, index: QModelIndex):
        directory = self.tableModel.dataFrame.iloc[index.row()]['Directory']
        if platform.system() == 'Windows':
            startfile(directory)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', directory])
        else:
            subprocess.Popen(['xdg-open', directory])
