import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pydantic import DirectoryPath, Field, validate_call
from pydantic_settings import BaseSettings, CliPositionalArg
from qtpy.QtCore import QFileSystemWatcher, QItemSelection, QModelIndex, QObject, QRectF, Qt, Signal, Slot
from qtpy.QtGui import QColor, QLinearGradient, QPainter, QTransform
from qtpy.QtWidgets import (
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
from iblrig.raw_data_loaders import bpod_session_data_to_dataframe, load_task_jsonable


class TrialsTableModel(DataFrameTableModel):
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any | None:
        if index.isValid() and role == Qt.ItemDataRole.StatusTipRole:
            trial = self.data(index.siblingAtColumn(0), Qt.ItemDataRole.DisplayRole)
            stim = self.data(index.siblingAtColumn(1), Qt.ItemDataRole.DisplayRole)
            outcome = self.data(index.siblingAtColumn(2), Qt.ItemDataRole.DisplayRole)
            timing = self.data(index.siblingAtColumn(3), Qt.ItemDataRole.DisplayRole)
            tip = (
                f'Trial {trial}: {abs(stim) * 100:g}% contrast on {"right" if np.sign(stim) == 1 else "left"} side '
                f'of screen, {outcome}'
            )
            return tip if outcome == 'no-go' else f'{tip} after {timing:0.2f} s'
        return super().data(index, role)


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
        table['Stimulus'] = np.sign(self._trial_data.position) * self._trial_data.contrast
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

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        value = index.data()
        color = QColor()
        color.setHslF(0, 0, 1.0 - abs(value))

        diameter = int(option.rect.height() * 0.8)
        spacing = (option.rect.height() - diameter) // 2
        x_pos = option.rect.left() + spacing if value < 0 else option.rect.right() - diameter - spacing
        y_pos = option.rect.top() + spacing

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(self.pen)
        painter.drawEllipse(x_pos, y_pos, diameter, diameter)  # Draw circle

    def displayText(self, value, locale):
        return ''


class ResponseTimeDelegate(QStyledItemDelegate):
    norm_min = 0.1
    norm_max = 60.0
    norm_div = np.log(norm_max / norm_min)
    color_correct = QColor(44, 162, 95)
    color_error = QColor(227, 74, 51)
    color_nogo = QColor(220, 220, 220)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        # Get the float value from the model
        value = index.data()
        status = index.sibling(index.row(), 2).data()

        # Draw the progress bar
        painter.fillRect(option.rect, option.backgroundBrush)
        if status == 'no-go':
            filled_rect = QRectF(option.rect)
            painter.setBrush(self.color_nogo)
        else:
            norm_value = np.log(value / self.norm_min) / self.norm_div
            filled_rect = QRectF(option.rect)
            filled_rect.setWidth(filled_rect.width() * norm_value)
            gradient = QLinearGradient(filled_rect.topLeft(), filled_rect.topRight())
            gradient.setColorAt(0, QColor(255, 255, 255, 0))
            gradient.setColorAt(1, self.color_correct if status == 'correct' else self.color_error)
            painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRect(filled_rect)

        # Draw the value text
        painter.setPen(Qt.black)
        value_text = f'{value:.2f}' if status != 'no-go' else 'N/A'
        painter.drawText(option.rect, Qt.AlignVCenter | Qt.AlignCenter, value_text)

    def displayText(self, value, locale):
        return ''


class StateRegionItem(pg.LinearRegionItem):
    statusMessage = Signal(str)

    def __init__(self, *args, stateName: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMovable(False)
        self.stateName = stateName

    def hoverEvent(self, ev):
        if ev.enter:
            self.statusMessage.emit(f'State: "{self.stateName}"')
        elif ev.exit:
            if not hasattr(ev, '_scenePos'):
                self.statusMessage.emit('')
            else:
                item = self.scene().itemAt(ev.scenePos(), QTransform())
                if not isinstance(item, QGraphicsRectItem):
                    self.statusMessage.emit('')


class BpodWidget(pg.GraphicsLayoutWidget):
    data = pd.DataFrame()
    colors = pg.colormap.get('glasbey_light', source='colorcet')
    labels: dict[str, pg.LabelItem] = dict()
    plots: dict[str, pg.PlotDataItem] = dict()
    viewBoxes: dict[str, pg.ViewBox] = dict()

    def __init__(self, *args, title: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.setRenderHints(QPainter.Antialiasing)
        self.setBackground('white')
        self.centralWidget.setSpacing(0)

        # add title
        if title is not None:
            self.centralWidget.nextRow()
            self.addLabel(title, col=1, color='k')

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
        self.plots[channel] = pg.PlotDataItem(pen='k', stepMode='right')
        self.plots[channel].setSkipFiniteCheck(True)
        self.viewBoxes[channel] = self.addViewBox(col=1)
        self.viewBoxes[channel].addItem(self.plots[channel])
        self.viewBoxes[channel].setMouseEnabled(x=True, y=False)
        self.viewBoxes[channel].sigXRangeChanged.connect(self.updateXRange)

    def setData(self, data: pd.DataFrame):
        self.data = data
        self.showTrial()
        self.drawStateRegionItems()

    def drawStateRegionItems(self):
        start = self.data[self.data.Type == 'TrialStart'].index[0]
        t0 = self.data[self.data.Type == 'StateStart']
        t1 = self.data[self.data.Type == 'StateEnd']

        # remove existing regions
        for view_box in self.viewBoxes.values():
            for item in view_box.allChildren():
                if isinstance(item, StateRegionItem):
                    view_box.removeItem(item)
                    item.deleteLater()

        pen = (0, 0, 0, 0)
        for state_idx, state in enumerate(self.data['State'].cat.categories):
            state_mask = t0['State'] == state
            t0_state = (t0.index[state_mask] - start).total_seconds().to_list()
            t1_state = (t1.index[state_mask] - start).total_seconds().to_list()
            brush = self.colors.getByIndex(state_idx)
            brush.setAlphaF(0.2)

            for times in zip(t0_state, t1_state, strict=False):
                for view_box in self.viewBoxes.values():
                    r = StateRegionItem(times, stateName=state, brush=brush, pen=pen)
                    r.statusMessage.connect(self.showStatusMessage)
                    view_box.addItem(r)

    @Slot(str)
    def showStatusMessage(self, string: str):
        self.window().statusBar().showMessage(string)

    def showTrial(self):
        limits = self.data[self.data['Type'].isin(['TrialStart', 'TrialEnd'])]
        limits = limits.index.total_seconds()
        self.limits = {'xMin': 0, 'xMax': limits[1] - limits[0], 'minXRange': 0.001}

        for channel in self.plots:
            values = self.data.loc[self.data.Channel == channel, 'Value']
            x = values.index.total_seconds().to_numpy() - limits[0]
            y = values.to_numpy()

            # Since Bpod only supports *changes* in the digital signals, we need
            # to extend the plots to the axes limits.
            if len(x) > 0:
                x = np.insert(x, 0, 0)
                x = np.append(x, limits[1])
                y = np.insert(y, 0, not y[0])
                y = np.append(y, y[-1])

            self.plots[channel].setData(x, y)
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

        self.statusBar().showMessage('')
        self.setWindowTitle('Online Plots')

        # the frame that contains all the plots
        frame = QFrame(self)
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet('background-color: rgb(255, 255, 255);')
        self.setCentralWidget(frame)

        # we use a grid layout to organize the different plots
        layout = QGridLayout(frame)
        layout.setSpacing(0)
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
        self.trials = QTableView(self)
        self.trials.setModel(self.model.table_model)
        self.trials.setMouseTracking(True)
        self.trials.verticalHeader().hide()
        self.trials.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.trials.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.trials.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        # self.trials.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.trials.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.trials.setStyleSheet('QHeaderView::section { border: none; background-color: white; }')
        self.trials.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.trials.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stimulusDelegate = StimulusDelegate()
        self.responseTimeDelegate = ResponseTimeDelegate()
        self.trials.setItemDelegateForColumn(1, self.stimulusDelegate)
        self.trials.setColumnHidden(2, True)
        self.trials.setItemDelegateForColumn(3, self.responseTimeDelegate)
        self.trials.setShowGrid(False)
        self.trials.setFrameShape(QTableView.NoFrame)
        self.trials.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.trials.setSelectionMode(QTableView.SingleSelection)
        self.trials.setSelectionBehavior(QTableView.SelectRows)
        self.trials.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        layout.addWidget(self.trials, 2, 0, 1, 1)

        # bpod data
        self.bpodWidget = BpodWidget(self, title='Bpod States and Input Channels')
        self.bpodWidget.setMinimumHeight(200)
        self.bpodWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(self.bpodWidget, 3, 0, 1, 2)

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

    app = QApplication([])

    window = OnlinePlotsView(Settings().directory)
    window.show()

    app.exec()


if __name__ == '__main__':
    online_plots_cli()
