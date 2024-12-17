import ctypes
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pydantic import DirectoryPath, Field, validate_call
from pydantic_settings import BaseSettings, CliPositionalArg
from qtpy.QtCore import (
    QCoreApplication,
    QFileSystemWatcher,
    QItemSelection,
    QModelIndex,
    QObject,
    QRect,
    QRectF,
    Qt,
    Signal,
    Slot,
)
from qtpy.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap, QTransform
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGraphicsRectItem,
    QGridLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStyledItemDelegate,
    QTableView,
)

from iblqt.core import DataFrameTableModel
from iblrig import __version__ as iblrig_version
from iblrig.gui import resources_rc  # noqa: F401
from iblrig.raw_data_loaders import bpod_session_data_to_dataframe, load_task_jsonable


class TrialsTableModel(DataFrameTableModel):
    """A table model that displays status tips for entries in the trials table."""

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any | None:
        if index.isValid() and role == Qt.ItemDataRole.StatusTipRole:
            trial = index.siblingAtColumn(0).data()
            position = index.siblingAtColumn(1).data()
            contrast = index.siblingAtColumn(2).data() * 100
            debias = index.siblingAtColumn(3).data()
            outcome = index.siblingAtColumn(4).data()
            timing = index.siblingAtColumn(5).data()
            tip = (
                f'Trial {trial}: {contrast:g}% contrast / {abs(position):g}° {"right" if position > 0 else "left"} '
                f'{"(debiasing) " if debias else ""}/ {outcome}'
            )
            return tip + ('.' if outcome == 'no-go' else f' after {timing:0.2f} s.')
        if index.isValid() and index.column() == 0 and role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        return super().data(index, role)


class TrialsTableView(QTableView):
    """A table view that shows a logarithmic x-grid in one column"""

    norm_min = 0.1
    norm_max = 102.0
    norm_div = np.log10(norm_max / norm_min)
    x_minor = [i / j for j in (10, 1, 0.1) for i in range(2, 10)]
    x_major = np.power(10.0, np.arange(-1, 3))
    color_minor = QColor(238, 238, 238)
    color_major = QColor(199, 199, 199)
    grid_col = 5

    def paintEvent(self, event):
        viewport_pos = self.columnViewportPosition(self.grid_col)
        col_width = self.columnWidth(self.grid_col)
        painter = QPainter(self.viewport())
        painter.setPen(self.color_minor)
        for x in self.x_minor:
            x_val = np.log10(x / self.norm_min) / self.norm_div
            line_x = viewport_pos + round(col_width * x_val)
            painter.drawLine(line_x, 0, line_x, self.height())
        painter.setPen(self.color_major)
        for x in self.x_major:
            x_val = np.log10(x / self.norm_min) / self.norm_div
            line_x = viewport_pos + round(col_width * x_val)
            painter.drawLine(line_x, 0, line_x, self.height())
        super().paintEvent(event)


class OnlinePlotsModel(QObject):
    currentTrialChanged = Signal(int)
    _trial_data = pd.DataFrame()
    _bpod_data = pd.DataFrame()
    trials_table = pd.DataFrame()
    table_model = TrialsTableModel()
    _jsonableOffset = 0
    _currentTrial = 0

    @validate_call(config=dict(arbitrary_types_allowed=True))
    def __init__(self, raw_data_folder: DirectoryPath, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.raw_data_folder = raw_data_folder
        self.jsonable_file = raw_data_folder.joinpath('_iblrig_taskData.raw.jsonable')
        self.settings_file = raw_data_folder.joinpath('_iblrig_taskSettings.raw.json')

        if not self.jsonable_file.exists():
            raise FileNotFoundError(self.jsonable_file)
        if not self.settings_file.exists():
            raise FileNotFoundError(self.settings_file)

        with self.settings_file.open('r') as f:
            self.task_settings = json.load(f)

        # read the jsonable file and instantiate a QFileSystemWatcher
        self.readJsonable(self.jsonable_file)
        self.jsonableWatcher = QFileSystemWatcher([str(self.jsonable_file)], parent=self)
        self.jsonableWatcher.fileChanged.connect(self.readJsonable)

    @Slot(str)
    def readJsonable(self, _: str) -> None:
        trial_data, bpod_data = load_task_jsonable(self.jsonable_file, offset=self._jsonableOffset)
        self._jsonableOffset = self.jsonable_file.stat().st_size
        self._trial_data = pd.concat([self._trial_data, trial_data])
        self._bpod_data = bpod_session_data_to_dataframe(bpod_data=bpod_data, existing_data=self._bpod_data)

        table = pd.DataFrame()
        table['Trial'] = self._trial_data.trial_num
        table['Stimulus'] = self._trial_data.position
        table['Contrast'] = self._trial_data.contrast
        table['Debias'] = self._trial_data.debias_trial if 'debias_trial' in self._trial_data.columns else False
        table['Outcome'] = self._trial_data.apply(
            lambda row: 'no-go' if row['response_side'] == 0 else ('correct' if row['trial_correct'] else 'error'), axis=1
        )
        table['Response Time / s'] = self._trial_data.apply(
            lambda row: np.NAN if row['response_side'] == 0 else row['response_time'], axis=1
        )
        self.table_model.setDataFrame(table)

        self.setCurrentTrial(self.nTrials() - 1)

    @Slot(int)
    def setCurrentTrial(self, value: int) -> None:
        if value != self._currentTrial:
            self._currentTrial = value
            self.currentTrialChanged.emit(value)

    def currentTrial(self) -> int:
        return self._currentTrial

    def nTrials(self) -> int:
        return len(self._trial_data)

    def bpod_data(self, trial: int) -> pd.DataFrame:
        return self._bpod_data[self._bpod_data.Trial == trial]


class StimulusDelegate(QStyledItemDelegate):
    pen = QColor(0, 0, 0, 128)

    def paint(self, painter, option, index: QModelIndex):
        super().paint(painter, option, index)
        location = index.siblingAtColumn(1).data()
        contrast = index.siblingAtColumn(2).data()
        debias = index.siblingAtColumn(3).data()

        color = QColor()
        color.setHslF(0, 0, 1.0 - contrast)

        diameter = round(option.rect.height() * 0.8)
        spacing = (option.rect.height() - diameter) // 2
        x_pos = option.rect.left() + spacing if location < 0 else option.rect.right() - diameter - spacing
        y_pos = option.rect.top() + spacing

        # draw circle
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(self.pen)
        painter.drawEllipse(x_pos, y_pos, diameter, diameter)

        if debias:
            rect = QRect(x_pos, y_pos, diameter, diameter)
            painter.setPen(QColor('white') if contrast > 0.5 else QColor('black'))
            painter.setFont(QFont(painter.font().family(), 9, -1, False))
            painter.drawText(rect, Qt.AlignHCenter | Qt.AlignVCenter, 'DB')
        painter.restore()

    def displayText(self, value, locale):
        return ''


class ResponseTimeDelegate(QStyledItemDelegate):
    norm_min = 0.1
    norm_max = 102.0
    norm_div = np.log(norm_max / norm_min)
    color_correct = QColor(44, 162, 95)
    color_error = QColor(227, 74, 51)
    color_nogo = QColor(192, 192, 192)
    color_text = QColor('white')
    color_gradient0 = QColor(255, 255, 255, 0)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        # Get the float value from the model
        value = index.data()
        outcome = index.sibling(index.row(), 4).data()

        # Draw the progress bar
        painter.fillRect(option.rect, option.backgroundBrush)
        if outcome == 'no-go':
            return
        norm_value = np.log(value / self.norm_min) / self.norm_div
        filled_rect = QRectF(option.rect)
        filled_rect.setWidth(filled_rect.width() * norm_value)
        gradient = QLinearGradient(filled_rect.topLeft(), filled_rect.topRight())
        gradient.setColorAt(0, self.color_gradient0)
        gradient.setColorAt(1, self.color_correct if outcome == 'correct' else self.color_error)
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRect(filled_rect)

        painter.setPen(self.color_text)
        value_text = f'{value:.2f}' if outcome != 'no-go' else 'N/A'
        filled_rect.adjust(0, 0, -5, 0)
        painter.drawText(filled_rect, Qt.AlignVCenter | Qt.AlignRight, value_text)

    def displayText(self, value, locale):
        return ''


class StateMeshItem(pg.PColorMeshItem):
    stateIndex = Signal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def hoverEvent(self, ev):
        if ev.exit:
            if not hasattr(ev, '_scenePos'):
                self.stateIndex.emit(-1)
            else:
                item = self.scene().itemAt(ev.scenePos(), QTransform())
                if not isinstance(item, QGraphicsRectItem):
                    self.stateIndex.emit(-1)
            return

        try:
            x = self.mapFromParent(ev.pos()).x()
        except AttributeError:
            return
        try:
            i = self.z[:, np.where(self.x[0, :] <= x)[0][-1]][0]
        except IndexError:
            return
        self.stateIndex.emit(i)


class BpodWidget(pg.GraphicsLayoutWidget):
    data = pd.DataFrame()
    labels: dict[str, pg.LabelItem] = dict()
    plots: dict[str, pg.PlotDataItem] = dict()
    meshes: dict[str, StateMeshItem] = dict()
    viewBoxes: dict[str, pg.ViewBox] = dict()

    def __init__(self, *args, title: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.setRenderHints(QPainter.Antialiasing)
        self.setBackground('white')
        self.centralWidget.setSpacing(0)
        self.centralWidget.setContentsMargins(0, 0, 0, 0)

        colormap = pg.colormap.get('glasbey_light', source='colorcet')
        colors = colormap.getLookupTable(0, 1, 256, alpha=True)
        colors[:, 3] = 64  # set alpha
        self.colormap = pg.ColorMap(colormap.pos, colors)

        # add title
        if title is not None:
            self.centralWidget.nextRow()
            self.addLabel(title, size='11pt', col=1, color='k')

        # add plots for digital channels
        for channel in ('BNC1', 'BNC2', 'Port1'):
            self.addDigitalChannel(channel)

        # add x axis
        self.centralWidget.nextRow()
        a = pg.AxisItem(orientation='bottom', textPen='k', linkView=list(self.viewBoxes.values())[0], parent=self.centralWidget)
        a.setLabel(text='Time', units='s')
        a.enableAutoSIPrefix(True)
        self.centralWidget.addItem(a, col=1)

    def addDigitalChannel(self, channel: str, label: str | None = None):
        label = channel if label is None else label
        self.centralWidget.nextRow()
        self.labels[channel] = self.addLabel(label, col=0, color='k')
        self.meshes[channel] = StateMeshItem(colorMap=self.colormap)
        self.meshes[channel].stateIndex.connect(self.showStateInfo)
        self.plots[channel] = pg.PlotDataItem(pen='k', stepMode='right')
        self.plots[channel].setSkipFiniteCheck(True)
        self.viewBoxes[channel] = self.addViewBox(col=1)
        self.viewBoxes[channel].addItem(self.meshes[channel])
        self.viewBoxes[channel].addItem(self.plots[channel])
        self.viewBoxes[channel].setMouseEnabled(x=True, y=False)
        self.viewBoxes[channel].setMenuEnabled(False)
        self.viewBoxes[channel].sigXRangeChanged.connect(self.updateXRange)

    def setData(self, data: pd.DataFrame):
        self.data = data
        self.showTrial()

    @Slot(int)
    def showStateInfo(self, index: int):
        if index < 0:
            self.window().statusBar().clearMessage()
        else:
            self.window().statusBar().showMessage(f'State: {self.data.State.cat.categories[index]}')

    def showTrial(self):
        limits = self.data[self.data['Type'].isin(['TrialStart', 'TrialEnd'])]
        limits = limits.index.total_seconds()
        self.limits = {'xMin': 0, 'xMax': limits[1] - limits[0], 'minXRange': 0.001, 'yMin': -0.2, 'yMax': 1.2}

        state_t0 = self.data[self.data.Type == 'StateStart']
        state_t1 = self.data[self.data.Type == 'StateEnd']
        mesh_x = np.append(state_t0.index.total_seconds(), state_t1.index[-1].total_seconds()) - limits[0]
        mesh_x = np.tile(mesh_x, (2, 1))
        mesh_y = np.zeros(mesh_x.shape) - 0.2
        mesh_y[1, :] = 1.2
        mesh_z = state_t0.State.cat.codes.to_numpy()
        mesh_z = mesh_z[np.newaxis, :]

        for channel in self.plots:
            values = self.data.loc[self.data.Channel == channel, 'Value']
            plot_x = values.index.total_seconds().to_numpy() - limits[0]
            plot_y = values.to_numpy()

            # Since Bpod only supports *changes* in the digital signals, we need
            # to extend the plots to the axes limits.
            if len(plot_x) > 0:
                plot_x = np.insert(plot_x, 0, 0)
                plot_x = np.append(plot_x, limits[1])
                plot_y = np.insert(plot_y, 0, not plot_y[0])
                plot_y = np.append(plot_y, plot_y[-1])

            self.plots[channel].setData(plot_x, plot_y)
            self.meshes[channel].setData(mesh_x, mesh_y, mesh_z)
            self.viewBoxes[channel].setLimits(**self.limits)

        list(self.viewBoxes.values())[0].setXRange(
            self.data.index[0].total_seconds(), self.data.index[-1].total_seconds(), padding=0
        )

    def updateXRange(self):
        sender = self.sender()
        x_range = sender.viewRange()[0]

        # Update the x-range for all other ViewBoxes
        for view_box in self.viewBoxes.values():
            if view_box is not sender:  # Avoid updating the sender
                view_box.setXRange(x_range[0], x_range[1], padding=0)


class OnlinePlotsView(QMainWindow):
    def __init__(self, raw_data_folder: DirectoryPath, parent: QObject | None = None):
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        self.model = OnlinePlotsModel(raw_data_folder, self)

        self.statusBar().clearMessage()
        self.setWindowTitle('Online Plots')
        self.setMinimumSize(1024, 768)
        icon = QIcon()
        icon.addPixmap(QPixmap(':/images/iblrig_logo'), QIcon.Normal, QIcon.Off)
        self.setWindowIcon(icon)

        # the frame that contains all the plots
        frame = QFrame(self)
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet('background-color: rgb(255, 255, 255);')
        self.setCentralWidget(frame)

        # we use a grid layout to organize the different widgets
        layout = QGridLayout(frame)
        frame.setLayout(layout)

        # main title
        self.title = QLabel('This is the main title')
        self.title.setAlignment(Qt.AlignHCenter)
        font = self.title.font()
        font.setPointSize(15)
        font.setBold(True)
        self.title.setFont(font)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(self.title, 0, 0, 1, 2)

        # sub title
        subtitle = QLabel('This is the sub-title')
        subtitle.setAlignment(Qt.AlignHCenter)
        subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(subtitle, 1, 0, 1, 2)

        # trial data
        self.trials = TrialsTableView(self)
        self.trials.setModel(self.model.table_model)
        self.trials.setMouseTracking(True)
        self.trials.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.trials.verticalHeader().hide()
        self.trials.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.trials.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.trials.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.trials.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.trials.horizontalHeader().setStretchLastSection(True)
        self.trials.setStyleSheet(
            'QHeaderView::section { border: none; background-color: white; }'
            'QTableView::item:selected { color: black; selection-background-color: rgb(229, 229, 229); }'
        )
        self.trials.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.trials.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stimulusDelegate = StimulusDelegate()
        self.responseTimeDelegate = ResponseTimeDelegate()
        self.trials.setItemDelegateForColumn(1, self.stimulusDelegate)
        self.trials.setColumnHidden(2, True)
        self.trials.setColumnHidden(3, True)
        self.trials.setColumnHidden(4, True)
        self.trials.setItemDelegateForColumn(5, self.responseTimeDelegate)
        self.trials.setShowGrid(False)
        self.trials.setFrameShape(QTableView.NoFrame)
        self.trials.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.trials.setSelectionMode(QTableView.SingleSelection)
        self.trials.setSelectionBehavior(QTableView.SelectRows)
        self.trials.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        layout.addWidget(self.trials, 2, 0, 2, 1)

        # psychometric function
        self.psychometricFunction = pg.PlotWidget(parent=self, background='white')
        self.psychometricFunction.plotItem.setTitle('Psychometric Function', color='k')
        self.psychometricFunction.plotItem.getAxis('left').setLabel('Rightward Choices (%)')
        self.psychometricFunction.plotItem.getAxis('bottom').setLabel('Signed Contrast')
        for axis in ('left', 'bottom'):
            self.psychometricFunction.plotItem.getAxis(axis).setGrid(128)
            self.psychometricFunction.plotItem.getAxis(axis).setTextPen('k')
        self.psychometricFunction.plotItem.setXRange(-1, 1, padding=0.05)
        self.psychometricFunction.plotItem.setYRange(0, 1, padding=0.05)
        self.psychometricFunction.plotItem.setMouseEnabled(x=False, y=False)
        self.psychometricFunction.plotItem.setMenuEnabled(False)
        self.psychometricFunction.plotItem.hideButtons()
        self.psychometricFunction.plotItem.addItem(pg.InfiniteLine(0.5, 0, 'black'))
        self.psychometricFunction.plotItem.addItem(pg.InfiniteLine(0, 90, 'black'))
        layout.addWidget(self.psychometricFunction, 2, 1, 1, 1)

        # chronometric function
        self.responseTimeWidget = pg.PlotWidget(parent=self, background='white')
        self.responseTimeWidget.plotItem.setTitle('Chronometric Function', color='k')
        self.responseTimeWidget.plotItem.getAxis('left').setLabel('Response Time (s)')
        self.responseTimeWidget.plotItem.getAxis('bottom').setLabel('Signed Contrast')
        for axis in ('left', 'bottom'):
            self.responseTimeWidget.plotItem.getAxis(axis).setGrid(128)
            self.responseTimeWidget.plotItem.getAxis(axis).setTextPen('k')
        self.responseTimeWidget.plotItem.setLogMode(x=False, y=True)
        self.responseTimeWidget.plotItem.setXRange(-1, 1, padding=0.05)
        self.responseTimeWidget.plotItem.setYRange(-1, 2, padding=0.05)
        self.responseTimeWidget.plotItem.setMouseEnabled(x=False, y=False)
        self.responseTimeWidget.plotItem.setMenuEnabled(False)
        self.responseTimeWidget.plotItem.hideButtons()
        self.responseTimeWidget.plotItem.addItem(pg.InfiniteLine(0, 90, 'black'))
        layout.addWidget(self.responseTimeWidget, 3, 1, 1, 1)

        # bpod data
        self.bpodWidget = BpodWidget(self, title='Bpod States and Input Channels')
        self.bpodWidget.setMinimumHeight(130)
        self.bpodWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(self.bpodWidget, 4, 0, 1, 2)

        self.model.currentTrialChanged.connect(self.updatePlots)

    @Slot(int)
    def updatePlots(self, trial: int):
        self.title.setText(f'Trial {trial}')
        self.bpodWidget.setData(self.model.bpod_data(trial))
        self.trials.setCurrentIndex(self.model.table_model.index(trial, 0))
        self.update()

    def onSelectionChanged(self, selected: QItemSelection, _: QItemSelection):
        self.model.setCurrentTrial(selected.indexes()[0].row())

    def keyPressEvent(self, event) -> None:
        """Navigate trials using directional keys."""
        match event.key():
            case Qt.Key.Key_Up:
                if self.model.currentTrial() > 0:
                    self.model.setCurrentTrial(self.model.currentTrial() - 1)
            case Qt.Key.Key_Down:
                if self.model.currentTrial() < (self.model.nTrials() - 1):
                    self.model.setCurrentTrial(self.model.currentTrial() + 1)
            case Qt.Key.Key_Home:
                self.model.setCurrentTrial(0)
            case Qt.Key.Key_End:
                self.model.setCurrentTrial(self.model.nTrials() - 1)
            case _:
                return
        event.accept()


def online_plots_cli():
    class Settings(BaseSettings, cli_parse_args=True):
        directory: CliPositionalArg[Path] = Field(description='Raw Data Directory')

    # set app information
    QCoreApplication.setOrganizationName('International Brain Laboratory')
    QCoreApplication.setOrganizationDomain('internationalbrainlab.org')
    QCoreApplication.setApplicationName('IBLRIG Online Plots')
    if os.name == 'nt':
        app_id = f'IBL.iblrig.online_plots.{iblrig_version}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication([])

    window = OnlinePlotsView(Settings().directory)
    window.show()

    app.exec()


if __name__ == '__main__':
    online_plots_cli()
