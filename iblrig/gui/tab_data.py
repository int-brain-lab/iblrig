import platform
import subprocess
from datetime import datetime
from typing import NamedTuple

import pandas as pd
from qtpy.QtCore import (
    QDateTime,
    QModelIndex,
    QRegExp,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QThread,
    Signal,
    Slot,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from iblqt.core import DataFrameTableModel
from iblrig.path_helper import get_local_and_remote_paths
from iblrig.transfer_experiments import CopyState, SessionCopier
from iblutil.util import dir_size, format_bytes

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
            data = index.data()
            option.text = format_bytes(int(data)) if isinstance(data, float) else ''
            option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter


class TabData(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = QSettings()
        self.local_subjects_path = get_local_and_remote_paths()['local_subjects_folder']
        self.remote_subjects_path = get_local_and_remote_paths()['remote_subjects_folder']

        # create empty DataFrameTableModel
        data = pd.DataFrame(None, index=[], columns=[c.name for c in COLUMNS])
        self.table_model = DataFrameTableModel(dataFrame=data)

        # create filter proxy & assign it to view
        self.table_proxy = QSortFilterProxyModel()
        self.table_proxy.setSourceModel(self.table_model)
        self.table_proxy.setFilterKeyColumn(1)

        # define worker for assembling data
        self.data_worker = DataWorker(self, self.table_model)
        self.data_worker.initialized.connect(self.table_model.setDataFrame)
        self.data_worker.update.connect(self.table_model.setData)
        self.data_worker.started.connect(lambda: button_update.setEnabled(False))
        self.data_worker.lazyLoadComplete.connect(lambda: button_update.setEnabled(True))

        # define table view
        self.table_view = QTableView(self)
        self.table_view.setModel(self.table_proxy)
        self.table_view.doubleClicked.connect(self._open_dir)
        self.table_view.setToolTip('Double-click a row to open the respective folder')
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table_view.setTabKeyNavigation(False)
        self.table_view.setProperty('showDropIndicator', False)
        self.table_view.setShowGrid(False)
        self.table_view.setSortingEnabled(True)
        self.table_view.setWordWrap(False)
        self.table_view.setItemDelegate(DataItemDelegate(self.table_view))
        self.table_view.sortByColumn(
            self.settings.value('sortColumn', [c.name for c in COLUMNS].index('Date'), int),
            self.settings.value('sortOrder', Qt.AscendingOrder, Qt.SortOrder),
        )

        # define table headers
        horizontal_header = self.table_view.horizontalHeader()
        horizontal_header.setCascadingSectionResizes(True)
        horizontal_header.setHighlightSections(False)
        horizontal_header.sectionClicked.connect(self._store_sort)
        horizontal_header.setDefaultAlignment(Qt.AlignLeft)
        for idx, column in enumerate(COLUMNS):
            self.table_view.setColumnHidden(idx, column.hidden)
            if not column.hidden:
                if column.resizeMode == QHeaderView.Fixed:
                    horizontal_header.resizeSection(idx, column.sectionWidth)
                else:
                    horizontal_header.setSectionResizeMode(idx, column.resizeMode)
        self.table_view.verticalHeader().setVisible(False)

        # define remaining widgets
        edit_filter = QLineEdit(self)
        edit_filter.setToolTip('Filter table by subject')
        edit_filter.setPlaceholderText('Filter by Subject')
        edit_filter.textChanged.connect(self._filter)
        button_update = QPushButton(self)
        button_update.setToolTip('Update table')
        button_update.setText('Update')
        button_update.clicked.connect(self.data_worker.start)

        # define layout
        horizontal_widget = QWidget(self)
        horizontal_layout = QHBoxLayout(horizontal_widget)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_layout.addWidget(edit_filter)
        horizontal_layout.addStretch(1)
        horizontal_layout.addWidget(button_update)
        vertical_layout = QVBoxLayout(self)
        vertical_layout.addWidget(self.table_view)
        vertical_layout.addWidget(horizontal_widget)

    @Slot(str)
    def _filter(self, text: str):
        self.table_proxy.setFilterRegExp(QRegExp(text, Qt.CaseInsensitive))

    def showEvent(self, a0):
        if self.table_model.rowCount() == 0:
            self.data_worker.initialize()

    @Slot(QModelIndex)
    def _open_dir(self, index: QModelIndex):
        source_index = self.table_proxy.mapToSource(index)
        directory = self.table_model.itemData(source_index.siblingAtColumn(0))[0]
        if platform.system() == 'Windows':
            startfile(directory)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', directory])
        else:
            subprocess.Popen(['xdg-open', directory])

    @Slot(int)
    def _store_sort(self, index: int):
        self.settings.setValue('sortColumn', self.table_view.horizontalHeader().sortIndicatorSection())
        self.settings.setValue('sortOrder', self.table_view.horizontalHeader().sortIndicatorOrder())


class DataWorker(QThread):
    initialized = Signal(pd.DataFrame)
    update = Signal(QModelIndex, object)
    lazyLoadComplete = Signal()

    def __init__(self, parent: TabData, model: DataFrameTableModel):
        super().__init__(parent)
        self.local_subjects_path = parent.local_subjects_path
        self.remote_subjects_path = parent.remote_subjects_path
        self.table_model = model
        self.col_size = self.table_model.getDataFrame().columns.get_loc('Size')
        self.col_status = self.table_model.getDataFrame().columns.get_loc('Copy Status')
        self.table_model.modelReset.connect(self.start)

    def initialize(self):
        data = []
        for session_dir in self.local_subjects_path.glob(SESSIONS_GLOB):
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
                    '',  # will be lazy-loaded in a separate step
                ]
            )
        data = pd.DataFrame(data=data, columns=[c.name for c in COLUMNS])
        self.initialized.emit(data)
        self.start()

    def run(self):
        for row, row_data in self.table_model.getDataFrame().iterrows():
            index = self.table_model.index(row, self.col_size)
            size = float(dir_size(row_data['Directory']))
            self.update.emit(index, size)
            state = SessionCopier(row_data['Directory'], remote_subjects_folder=self.remote_subjects_path).state
            state = COPY_STATE_STRINGS.get(state, 'N/A')
            index = self.table_model.index(row, self.col_status)
            self.update.emit(index, state)
        self.lazyLoadComplete.emit()
