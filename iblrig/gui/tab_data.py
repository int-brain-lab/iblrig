import platform
import subprocess
from datetime import datetime
from typing import NamedTuple
if platform.system() == 'Windows':
    from os import startfile

import pandas as pd
from PyQt5.Qt import pyqtSlot
from PyQt5.QtCore import (
    QAbstractTableModel,
    QDateTime,
    QModelIndex,
    QRegExp,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QThread,
    QThreadPool,
    pyqtSignal,
)
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
    sectionWidth: int = 120


COLUMNS = (
    Column(name='Directory', hidden=True),
    Column(name='Subject', resizeMode=QHeaderView.Stretch),
    Column(name='Date'),
    Column(name='Copy Status'),
    Column(name='Size', sectionWidth=60),
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
        self._localSubjectsPath = get_local_and_remote_paths().local_subjects_folder
        self._sessionStatesThread = None

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

        # connect signals to slots
        self.tableView.doubleClicked.connect(self._openDir)
        self.tableView.horizontalHeader().sectionClicked.connect(self._storeSort)
        self.pushButtonUpdate.clicked.connect(self._initializeData)
        self.lineEditFilter.textChanged.connect(self._filter)

    @pyqtSlot(str)
    def _filter(self, text: str):
        self.tableProxy.setFilterRegExp(QRegExp(text, Qt.CaseInsensitive))

    def showEvent(self, a0):
        if self.tableModel.rowCount() == 0:
            self._initializeData()

    def _initializeData(self):
        worker = Worker(self._initializeDataJob)
        worker.signals.result.connect(self._onUpdateDataResult)
        QThreadPool.globalInstance().start(worker)

    def _initializeDataJob(self):
        data = []
        for session_dir in (d for d in self._localSubjectsPath.glob(SESSIONS_GLOB) if d.is_dir()):
            subject = session_dir.parents[1].name
            size = float(dir_size(session_dir))  # save as float as int seems to cause issues with sorting
            # copy_state = SessionCopier(session_dir).state
            # copy_state_string = COPY_STATE_STRINGS.get(copy_state, 'N/A')

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
                    'Copy Status': '',
                    'Size': size,
                }
            )
        data = pd.DataFrame(data)
        assert [c for c in data.columns] == [c.name for c in COLUMNS]
        return data

    def _onUpdateDataResult(self, data: pd.DataFrame):
        self.tableModel.setDataFrame(data)
        self._sessionStatesThread = SessionStatesWorker(self.tableModel)
        self._sessionStatesThread.update.connect(self._updateTableModel)
        self._sessionStatesThread.start()

    def _updateTableModel(self, index: QModelIndex, state: str):
        self.tableModel.setData(index, state)

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


class SessionStatesWorker(QThread):
    update = pyqtSignal(QModelIndex, str)

    def __init__(self, model):
        super().__init__()
        self._model: QAbstractTableModel = model

    def run(self):
        self._model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        for row in range(self._model.rowCount()):
            index = self._model.index(row, [c.name for c in COLUMNS].index('Directory'))
            directory = self._model.data(index, Qt.DisplayRole)
            state = SessionCopier(directory).state
            state = COPY_STATE_STRINGS.get(state, 'N/A')
            index = self._model.index(row, [c.name for c in COLUMNS].index('Copy Status'))
            self.update.emit(index, state)
