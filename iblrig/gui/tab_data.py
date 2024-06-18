import operator

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QVariant, Qt
from PyQt5.QtWidgets import QWidget, QAbstractScrollArea

from iblrig.gui.ui_tab_data import Ui_TabData


class TabData(QWidget, Ui_TabData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.model = DataFrameTableModel()
        self.tableView.setModel(self.model)
        self.tableView.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

    def resizeEvent(self, a0):
        self.tableView.resizeColumnsToContents()
        self.tableView.resizeRowsToContents()


class DataFrameTableModel(QAbstractTableModel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.array_data = [['Mickey', '2', '3', '4', '5'], ['a', 'b', 'c', 'd', 'e']]
        self.header_data = ['Subject', 'Date', 'Index', 'Task(s)', 'Status']

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header_data[section])
        return QVariant()

    def rowCount(self, parent: QModelIndex = ...):
        return len(self.array_data)

    def columnCount(self, parent: QModelIndex = ...):
        return len(self.array_data[0])

    def data(self, index: QModelIndex, role: int = ...):
        if not index.isValid():
            return QVariant()
        elif role != Qt.DisplayRole:
            return QVariant()
        return QVariant(self.array_data[index.row()][index.column()])

    def sort(self, column: int, order: Qt.SortOrder = ...):
        self.layoutAboutToBeChanged.emit()
        self.array_data = sorted(self.array_data, key=operator.itemgetter(column))
        if order == Qt.DescendingOrder:
            self.array_data.reverse()
        self.layoutChanged.emit()
