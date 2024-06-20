import platform
import subprocess
from datetime import datetime
from os import startfile
from pathlib import Path
from typing import NamedTuple

import pandas as pd
from PyQt5.Qt import pyqtSlot
from PyQt5.QtCore import QModelIndex, Qt, QThreadPool, QDateTime, QSortFilterProxyModel, QRegExp
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

SESSIONS_GLOB = r'*/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/[0-9][0-9][0-9]/'


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "K", "M", "G", "T", "P", "E", "Z"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Y{suffix}"


class Column(NamedTuple):
    name: str
    hidden: bool = False
    resizeMode: QHeaderView.ResizeMode = QHeaderView.ResizeToContents


class DataItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        header_text = index.model().headerData(index.column(), Qt.Horizontal, Qt.DisplayRole)
        if 'Size' in header_text:
            option.text = sizeof_fmt(index.data())
            option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter


class TabData(QWidget, Ui_TabData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self._localSubjectsPath = get_local_and_remote_paths().local_subjects_folder

        # define columns
        self._columns = (
            Column(name='Directory', hidden=True),
            Column(name='Subject', resizeMode=QHeaderView.Stretch),
            Column(name='Date'),
            Column(name='Copy Status'),
            Column(name='Size'),
        )

        # create empty DataFrameTableModel
        data = pd.DataFrame(None, index=[], columns=[c.name for c in self._columns])
        self.tableModel = DataFrameTableModel(df=data)
        #
        # # create filter proxy & assign it to view
        # self.tableProxy = QSortFilterProxyModel()
        # self.tableProxy.setSourceModel(self.tableModel)
        # self.tableProxy.setFilterKeyColumn(1)
        self.tableView.setModel(self.tableModel)

        # set properties of view's columns
        for idx, column in enumerate(self._columns):
            self.tableView.setColumnHidden(idx, column.hidden)
            if not column.hidden:
                self.tableView.horizontalHeader().setSectionResizeMode(idx, column.resizeMode)
        self.tableView.setItemDelegate(DataItemDelegate(self.tableView))

        # connect signals to slots
        self.tableView.doubleClicked.connect(self._openDir)
        self.pushButtonUpdate.clicked.connect(self.updateData)
        self.lineEditFilter.textChanged.connect(self._filter)

    @pyqtSlot(str)
    def _filter(self, text):
        self.tableProxy.setFilterRegExp(QRegExp(text, Qt.CaseInsensitive))

    def showEvent(self, a0):
        if self.tableModel.rowCount() == 0:
            self.updateData()

    def updateData(self):
        worker = Worker(self._updateData)
        worker.signals.result.connect(self._onUpdateDataResult)
        QThreadPool.globalInstance().start(worker)

    def _updateData(self):
        data = []
        for session_dir in (d for d in self._localSubjectsPath.glob(SESSIONS_GLOB) if d.is_dir()):
            subject = session_dir.parents[1].name
            size = dir_size(session_dir)
            copy_state = SessionCopier(session_dir).state
            copy_state_string = COPY_STATE_STRINGS.get(copy_state, 'N/A')

            # try to get folder creation time (cross-check with date-string of directory)
            date = datetime.strptime(session_dir.parent.name, '%Y-%m-%d')
            time = datetime.fromtimestamp(session_dir.stat().st_ctime)
            date = time if time.date() == date.date() else date
            date = QDateTime.fromTime_t(int(date.timestamp()))

            data.append(
                {
                    'Directory': session_dir,
                    'Subject': subject,
                    'Date': date,
                    'Copy Status': copy_state_string,
                    'Size': size,
                }
            )
        data = pd.DataFrame(data)
        assert [c for c in data.columns] == [c.name for c in self._columns]
        return data

    def _onUpdateDataResult(self, data: pd.DataFrame):
        self.tableModel.setDataFrame(data)
        header = self.tableView.horizontalHeader()
        self.tableView.sortByColumn(header.sortIndicatorSection(), header.sortIndicatorOrder())

    def _openDir(self, index: QModelIndex):
        directory = self.tableView.model().itemData(index.siblingAtColumn(0))[0]
        if platform.system() == 'Windows':
            startfile(directory)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', directory])
        else:
            subprocess.Popen(['xdg-open', directory])
