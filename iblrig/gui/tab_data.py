import platform
import subprocess
from datetime import datetime
from typing import NamedTuple

import pandas as pd
from PyQt5.Qt import pyqtSlot
from PyQt5.QtCore import (
    QDateTime,
    QModelIndex,
    QRegExp,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QThread,
    pyqtSignal,
)
from PyQt5.QtWidgets import QHeaderView, QStyledItemDelegate, QWidget

from iblrig.gui.tools import DataFrameTableModel
from iblrig.gui.ui_tab_data import Ui_TabData
from iblrig.path_helper import get_local_and_remote_paths
from iblrig.transfer_experiments import CopyState, SessionCopier
from iblutil.util import dir_size

if platform.system() == 'Windows':
    from os import startfile

COPY_STATE_STRINGS = {
    CopyState.HARD_RESET: 'Hard Reset',
    CopyState.NOT_REGISTERED: 'Not Registered',
    CopyState.PENDING: 'Copy Pending',
    CopyState.COMPLETE: 'Copy Complete',
    CopyState.FINALIZED: 'Copy Finalized',
}

SESSIONS_GLOB = r'*/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/[0-9][0-9][0-9]/'


def sizeof_fmt(num, suffix='B'):
    for unit in ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z'):
        if abs(num) < 1024.0:
            return f'{num:3.1f} {unit}{suffix}'
        num /= 1024.0
    return f'{num:.1f} Y{suffix}'


class Column(NamedTuple):
    name: str
    hidden: bool = False
    resizeMode: QHeaderView.ResizeMode = QHeaderView.Fixed
    sectionWidth: int = 130


COLUMNS = (
    Column(name='Directory', hidden=True),
    Column(name='Subject', resizeMode=QHeaderView.Stretch),
    Column(name='Date'),
    Column(name='Copy Status', sectionWidth=100),
    Column(name='Size', sectionWidth=75),
)


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
        self.settings = QSettings()
        self.localSubjectsPath = get_local_and_remote_paths().local_subjects_folder

        # create empty DataFrameTableModel
        data = pd.DataFrame(None, index=[], columns=[c.name for c in COLUMNS])
        self.tableModel = DataFrameTableModel(df=data)

        # create filter proxy & assign it to view
        self.tableProxy = QSortFilterProxyModel()
        self.tableProxy.setSourceModel(self.tableModel)
        self.tableProxy.setFilterKeyColumn(1)

        # define view
        self.tableView.setModel(self.tableProxy)
        header = self.tableView.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft)
        for idx, column in enumerate(COLUMNS):
            self.tableView.setColumnHidden(idx, column.hidden)
            if not column.hidden:
                if column.resizeMode == QHeaderView.Fixed:
                    header.resizeSection(idx, column.sectionWidth)
                else:
                    header.setSectionResizeMode(idx, column.resizeMode)
        self.tableView.setItemDelegate(DataItemDelegate(self.tableView))
        self.tableView.sortByColumn(
            self.settings.value('sortColumn', [c.name for c in COLUMNS].index('Date'), int),
            self.settings.value('sortOrder', Qt.AscendingOrder, Qt.SortOrder),
        )

        # define worker for assembling data
        self.dataWorker = DataWorker(self)

        # connect signals to slots
        self.dataWorker.initialized.connect(self.tableModel.setDataFrame)
        self.dataWorker.update.connect(self.tableModel.setData)
        self.dataWorker.started.connect(lambda: self.pushButtonUpdate.setEnabled(False))
        self.dataWorker.lazyLoadComplete.connect(lambda: self.pushButtonUpdate.setEnabled(True))
        self.tableView.doubleClicked.connect(self._openDir)
        self.tableView.horizontalHeader().sectionClicked.connect(self._storeSort)
        self.pushButtonUpdate.clicked.connect(self.dataWorker.start)
        self.lineEditFilter.textChanged.connect(self._filter)

    @pyqtSlot(str)
    def _filter(self, text: str):
        self.tableProxy.setFilterRegExp(QRegExp(text, Qt.CaseInsensitive))

    def showEvent(self, a0):
        if self.tableModel.rowCount() == 0:
            self.dataWorker.start()

    @pyqtSlot(QModelIndex)
    def _openDir(self, index: QModelIndex):
        directory = self.tableView.model().itemData(index.siblingAtColumn(0))[0]
        if platform.system() == 'Windows':
            startfile(directory)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', directory])
        else:
            subprocess.Popen(['xdg-open', directory])

    @pyqtSlot(int)
    def _storeSort(self, index: int):
        self.settings.setValue('sortColumn', self.tableView.horizontalHeader().sortIndicatorSection())
        self.settings.setValue('sortOrder', self.tableView.horizontalHeader().sortIndicatorOrder())


class DataWorker(QThread):
    initialized = pyqtSignal(pd.DataFrame)
    update = pyqtSignal(QModelIndex, object)
    lazyLoadComplete = pyqtSignal()

    def __init__(self, parent: TabData):
        super().__init__(parent)
        self.localSubjectsPath = parent.localSubjectsPath
        self.tableModel = parent.tableModel
        self.tableModel.modelReset.connect(self.lazyLoadStatus)

    def run(self):
        data = []
        for session_dir in self.localSubjectsPath.glob(SESSIONS_GLOB):
            # make sure we're dealing with a directory
            if not session_dir.is_dir():
                continue

            # get folder creation time (cross-check with name of directory)
            date = datetime.strptime(session_dir.parent.name, '%Y-%m-%d')
            time = datetime.fromtimestamp(session_dir.stat().st_ctime)
            date = time if time.date() == date.date() else date

            # append data
            data.append(
                [
                    session_dir,
                    session_dir.parents[1].name,
                    QDateTime.fromTime_t(int(date.timestamp())),
                    '',  # will be lazy-loaded in a separate step
                    float(dir_size(session_dir)),
                ]
            )
        data = pd.DataFrame(data=data, columns=[c.name for c in COLUMNS])
        self.initialized.emit(data)

    def lazyLoadStatus(self):
        col_status = self.tableModel.dataFrame.columns.get_loc('Copy Status')
        for row, row_data in self.tableModel.dataFrame.iterrows():
            state = SessionCopier(row_data['Directory']).state
            state = COPY_STATE_STRINGS.get(state, 'N/A')
            index = self.tableModel.index(row, col_status)
            self.update.emit(index, state)
        self.lazyLoadComplete.emit()
