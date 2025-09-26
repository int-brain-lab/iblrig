import ctypes
import datetime
import json
import os
import sys
import time
from collections.abc import Iterable
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pydantic import UUID4, AfterValidator, DirectoryPath, Field, FilePath, PlainSerializer, validate_call
from pydantic_settings import BaseSettings, CliPositionalArg
from qtpy.QtCore import (
    QCoreApplication,
    QFileSystemWatcher,
    QItemSelection,
    QModelIndex,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from qtpy.QtGui import QBrush, QColor, QFont, QGradient, QIcon, QLinearGradient, QPainter, QPixmap, QTransform
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsRectItem,
    QGraphicsSceneHoverEvent,
    QGridLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from iblqt.core import DataFrameTableModel, Worker
from iblrig import __version__ as iblrig_version
from iblrig.choiceworld import get_subject_training_info
from iblrig.gui import resources_rc  # noqa: F401
from iblrig.misc import online_std
from iblrig.path_helper import get_local_and_remote_paths
from iblrig.raw_data_loaders import bpod_trial_data_to_dataframe, load_task_jsonable
from one.alf.spec import is_session_path
from one.api import ONE


def is_alf_path(value: Path) -> Path:
    if not is_session_path(value):
        raise ValueError('Field is not a session path')
    return value


SessionPath = Annotated[
    Path,
    AfterValidator(lambda x: is_alf_path(x)),
    PlainSerializer(lambda x: str(x), return_type=str),
]


@dataclass
class Colors:
    RED = '#eb5757'
    GREEN = '#57eb8b'
    YELLOW = '#ede34e'
    TRANSPARENT = 'transparent'


@dataclass
class EngagedCriterion:
    SECONDS = 45 * 60
    TRIAL_COUNT = 400


@dataclass
class DefaultSettings:
    CONTRAST_SET = np.array([0, 1 / 16, 1 / 8, 1 / 4, 1 / 2, 1])
    PROBABILITY_SET = np.array([0.2, 0.5, 0.8])


class PlotWidget(pg.PlotWidget):
    """PyQtGraph PlotWidget with tuned default settings."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setBackground('white')
        self.plotItem.getViewBox().setBackgroundColor(pg.mkColor(250, 250, 250))
        self.plotItem.setMouseEnabled(x=False, y=False)
        self.plotItem.setMenuEnabled(False)
        self.plotItem.hideButtons()
        for axis in ('left', 'bottom'):
            self.plotItem.getAxis(axis).setTextPen('k')


class SingleBarChartWidget(PlotWidget):
    """A bar chart with a single column for use with PyQtGraph"""

    _font = QFont('Helvetica', 18, QFont.Bold)

    def __init__(self, *args, barColor: Any = 0.2, textColor: Any = 1.0, textFormat: str = '{:g}', **kwargs):
        super().__init__(*args, **kwargs)

        y_axis = self.plotItem.getAxis('left')
        y_axis.setWidth(40)
        y_axis.setGrid(128)

        x_axis = self.plotItem.getAxis('bottom')
        x_axis.setLabel(' ')
        x_axis.setTicks([[(1, ' ')], []])
        x_axis.setStyle(tickLength=0, tickAlpha=0)
        self.plotItem.setXRange(min=0, max=2, padding=0)

        bar_color = pg.mkColor(barColor)
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(0.9, bar_color)
        bar_color.setAlpha(128)
        gradient.setColorAt(0, bar_color)
        self._barGraphItem = pg.BarGraphItem(x=1, width=2, height=0, pen=None, brush=QBrush(gradient))
        self.addItem(self._barGraphItem)

        self._textFormat = textFormat
        self._textItem = pg.TextItem('0', anchor=(0.5, 0), color=textColor)
        self._textItem.setX(1)
        self._textItem.setY(50)
        self._textItem.setFont(self._font)
        self.addItem(self._textItem)

    @Slot(float)
    def setValue(self, value: float):
        self._barGraphItem.setOpts(height=value)
        self._textItem.setText(self._textFormat.format(value))
        self._textItem.setY(min(self.plotItem.viewRange()[1][1], value))
        self._setTextAnchor()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, '_textItem'):
            self._setTextAnchor()

    def _setTextAnchor(self):
        """Anchor _textItem above or below upper edge of _barGraphItem, depending on available space"""
        bar_height_px = self.height() / self.viewRect().height() * self._barGraphItem.boundingRect().height()
        if self._textItem.boundingRect().height() > bar_height_px:
            self._textItem.setAnchor((0.5, 1))
            self._textItem.setColor('black')
        else:
            self._textItem.setAnchor((0.5, 0))
            self._textItem.setColor('white')


class FunctionWidget(PlotWidget):
    """A widget for psychometric and chronometric functions"""

    def __init__(self, *args, colors: pg.ColorMap, probabilities: Iterable[float], **kwargs):
        super().__init__(*args, **kwargs)
        self.plotItem.addItem(pg.InfiniteLine(0, 90, 'black'))
        for axis in ('left', 'bottom'):
            self.plotItem.getAxis(axis).setGrid(128)
            self.plotItem.getAxis(axis).setTextPen('k')
        self.plotItem.getAxis('bottom').setLabel('Signed Contrast')
        legend = pg.LegendItem(pen='lightgray', brush='w', offset=(45, 35), verSpacing=-5, labelTextColor='k')
        legend.setParentItem(self.plotItem.graphicsItem())
        legend.setZValue(1)
        self.plotDataItems = dict()
        self.upperCurves = dict()
        self.lowerCurves = dict()
        self.fillItems = dict()
        null_pen = pg.mkPen((0, 0, 0, 0))
        for idx, p in enumerate(probabilities):
            line_color = colors.getByIndex(idx)
            fill_color = copy(line_color)
            fill_color.setAlpha(32)
            self.upperCurves[p] = self.plotItem.plot(pen=null_pen)
            self.lowerCurves[p] = self.plotItem.plot(pen=null_pen)
            self.fillItems[p] = pg.FillBetweenItem(self.upperCurves[p], self.lowerCurves[p], brush=fill_color, pen=null_pen)
            self.addItem(self.fillItems[p])
            self.plotDataItems[p] = self.plotItem.plot(connect='all')
            self.plotDataItems[p].setData(x=[1, np.NAN], y=[np.NAN, 1])
            self.plotDataItems[p].setPen(pg.mkPen(color=line_color, width=4))
            self.plotDataItems[p].setSymbol('o')
            self.plotDataItems[p].setSymbolPen(line_color)
            self.plotDataItems[p].setSymbolBrush(line_color.lighter(150))
            self.plotDataItems[p].setSymbolSize(4)
            legend.addItem(self.plotDataItems[p], f'p = {p:0.1f}')


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
                f'{"/ debiasing " if debias else ""}/ {outcome}'
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

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.setMouseTracking(True)
        # self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalHeader().hide()
        self.horizontalHeader().hide()
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setStretchLastSection(True)
        self.setStyleSheet(
            'QHeaderView::section { border: none; background-color: white; }'
            'QTableView::item:selected { color: black; selection-background-color: rgba(0, 0, 0, 6%); }'
            'QTableView { background-color: rgba(0, 0, 0, 3%); }'
        )
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stimulusDelegate = StimulusDelegate()
        self.responseTimeDelegate = ResponseTimeDelegate()
        self.setItemDelegateForColumn(1, self.stimulusDelegate)
        self.setItemDelegateForColumn(5, self.responseTimeDelegate)
        self.setShowGrid(False)
        self.setFrameShape(QTableView.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setSelectionBehavior(QTableView.SelectRows)

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


class TrialsWidget(QWidget):
    trialSelected = Signal(int)

    def __init__(self, parent: QObject, model: TrialsTableModel):
        super().__init__(parent)
        self.model = model

        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 7, 0, 36)
        self.setLayout(layout)

        self.titleLabel = QLabel('Trials History')
        self.titleLabel.setAlignment(Qt.AlignHCenter)
        font = self.titleLabel.font()
        font.setPointSize(11)
        self.titleLabel.setFont(font)
        layout.addWidget(self.titleLabel)

        self.table_view = TrialsTableView(self)
        self.table_view.setModel(self.model)
        self.table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.setColumnHidden(2, True)
        self.table_view.setColumnHidden(3, True)
        self.table_view.setColumnHidden(4, True)
        self.table_view.selectionModel().selectionChanged.connect(self._onSelectionChange)
        layout.addWidget(self.table_view)
        layout.setStretch(1, 1)

    @Slot(QItemSelection, QItemSelection)
    def _onSelectionChange(self, selected: QItemSelection, _deselected: QItemSelection):
        self.trialSelected.emit(selected.indexes()[0].row())


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
    color_correct = QColor(0, 107, 90)
    color_error = QColor(219, 67, 37)
    color_nogo = QColor(192, 192, 192)
    color_text = QColor('white')

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
        painter.setBrush(self.color_correct if outcome == 'correct' else self.color_error)
        painter.setPen(Qt.NoPen)
        painter.drawRect(filled_rect)

        painter.setPen(self.color_text)
        value_text = f'{value:.2f}' if outcome != 'no-go' else 'N/A'
        filled_rect.adjust(0, 0, -5, 0)
        painter.drawText(filled_rect, Qt.AlignVCenter | Qt.AlignRight, value_text)

    def displayText(self, value, locale):
        return ''


class StateMeshItem(pg.PColorMeshItem):
    """
    A graphical item for displaying a color mesh that represents Bpod states.

    This class extends the PyQtGraph's `PColorMeshItem` to provide
    functionality for emitting signals when the mouse hovers over
    different states in the mesh.

    Attributes
    ----------
    stateIndex : Signal
        A signal that emits the index of the state currently hovered over.
    """

    stateIndex = Signal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def hoverEvent(self, ev: QGraphicsSceneHoverEvent):
        """
        Handle hover events over the mesh item.

        This method emits the index of the state that the mouse is currently
        hovering over. If the mouse exits the item or hovers over an area
        that does not correspond to a state, it emits -1.

        Parameters
        ----------
        ev : QGraphicsSceneHoverEvent
            The event object containing information about the hover event.
        """
        if ev.exit:
            # If the mouse exits the item, emit -1 to indicate no state is hovered
            if not hasattr(ev, '_scenePos'):
                self.stateIndex.emit(-1)
            else:
                item = self.scene().itemAt(ev.scenePos(), QTransform())
                if not isinstance(item, QGraphicsRectItem):
                    self.stateIndex.emit(-1)
            return

        try:
            # Get the x-coordinate of the mouse position relative to the item
            x = self.mapFromParent(ev.pos()).x()
        except AttributeError:
            return
        try:
            # Find the index of the state corresponding to the x-coordinate
            i = self.z[:, np.where(self.x[0, :] <= x)[0][-1]][0]
        except IndexError:
            return

        # Emit the index of the hovered state
        self.stateIndex.emit(i)


class BpodWidget(pg.GraphicsLayoutWidget):
    """
    A widget for visualizing Bpod data in a graphical layout.

    This widget displays digital channels and Bpod states over time,
    allowing for the visualization of trial data.
    """

    data = pd.DataFrame()
    labels: dict[str, pg.LabelItem] = dict()
    plots: dict[str, pg.PlotDataItem] = dict()
    meshes: dict[str, StateMeshItem] = dict()
    viewBoxes: dict[str, pg.ViewBox] = dict()

    def __init__(
        self,
        *args,
        title: str | None = None,
        alpha: int = 64,
        channels: Iterable | None = None,
        showStatusTips: bool = True,
        **kwargs,
    ):
        """
        Initialize the BpodWidget.

        Parameters
        ----------
        *args : tuple
            Positional arguments to be passed to the parent class.
        title : str | None, optional
            The title of the widget (default is None).
        alpha : int, optional
            The alpha value used in color-coding the Bpod states. Default: 64.
        channels : Iterable, optional
            An iterable of channel names to be included in the plot.
            Defaults are `BNC1`, `BNC2`, and `Port1`.
        showStatusTips : bool, optional
            Show status tips when hovering the mouse over state regions. Default: True
        **kwargs : dict
            Keyword arguments to be passed to the parent class.
        """
        super().__init__(*args, **kwargs)

        # set rendering hint and layout options
        self.setRenderHints(QPainter.Antialiasing)
        self.setBackground('white')
        self.centralWidget.setSpacing(0)
        self.centralWidget.setContentsMargins(0, 0, 0, 0)

        # define colormap for Bpod states
        colormap = pg.colormap.get('glasbey_light', source='colorcet')
        colors = colormap.getLookupTable(0, 1, 256, alpha=True)
        colors[:, 3] = alpha
        self.colormap = pg.ColorMap(colormap.pos, colors)

        # add title
        if title is not None:
            self.centralWidget.nextRow()
            self.addLabel(title, size='11pt', col=1, color='k')

        # add digital channels
        for channel in channels or ('BNC1', 'BNC2', 'Port1'):
            self.addDigitalChannel(channel)

        # add x axis
        self.centralWidget.nextRow()
        a = pg.AxisItem(orientation='bottom', textPen='k', linkView=list(self.viewBoxes.values())[0], parent=self.centralWidget)
        a.setLabel(text='Time', units='s')
        a.enableAutoSIPrefix(True)
        self.centralWidget.addItem(a, col=1)

    def addDigitalChannel(self, channel: str, label: str | None = None):
        """
        Add a digital channel to the widget.

        Parameters
        ----------
        channel : str
            The name of the digital channel to add.
        label : str | None, optional
            The label for the channel (default is None, which uses the channel name).
        """
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
        """
        Set the data for the widget and update the display.

        Parameters
        ----------
        data : pd.DataFrame
            The data to be displayed in the widget. The data needs to be organized according to the format returned by
            :py:func:`~iblrig.raw_data_loaders.bpod_trial_data_to_dataframe`.
        """
        self.data = data
        self.showTrial()

    @Slot(int)
    def showStateInfo(self, index: int):
        """
        Show information about the state in the status bar.

        Parameters
        ----------
        index : int
            The index of the state to display.
        """
        if index < 0:
            self.window().statusBar().clearMessage()
        else:
            self.window().statusBar().showMessage(f'State: {self.data.State.cat.categories[index]}')

    def showTrial(self):
        """
        Display the trial data in the widget.
        This method updates the limits and plots for each digital channel.
        """
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

            # Extend the plots to both sides to include axes limits.
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


class OnlinePlotsModel(QObject):
    currentTrialChanged = Signal(int)
    titleChanged = Signal(str)
    titleColorChanged = Signal(str)
    sessionStringAvailable = Signal(str)
    tableModel = TrialsTableModel()
    sessionString = ''
    probability_set = DefaultSettings.PROBABILITY_SET
    contrast_set = DefaultSettings.CONTRAST_SET
    _trial_data = pd.DataFrame()
    _bpod_data: list[pd.DataFrame] = list()
    _jsonable_offset = 0
    _current_trial = 0

    @validate_call(config=dict(arbitrary_types_allowed=True))
    def __init__(self, session: FilePath | DirectoryPath | UUID4, parent: QObject | None = None):
        super().__init__(parent=parent)
        is_live = False

        # If session is a UUID ...
        if not isinstance(session, Path):
            one = ONE()

            # assert that session exists
            session_exists = len(one.alyx.rest('sessions', 'list', id=session)) > 0
            if not session_exists:
                raise ValueError(f'Could not find session with ID {session}')

            # load Task Data File
            datasets = one.list_datasets(session, filename='*taskData.raw.jsonable')
            if len(datasets) == 0:
                raise ValueError(f'Could not find Task Data File for session {session}')
            session = one.load_dataset(session, datasets[0], download_only=True)

            # load Task Settings File
            datasets = one.list_datasets(session, filename='*_iblrig_taskSettings.raw.json')
            if len(datasets) > 0:
                one.load_dataset(session, datasets[0], download_only=True)

        # If session is a directory ...
        if session.is_dir():
            if not session.name.startswith('raw_task_data'):
                raise ValueError(f'Not a Raw Data Directory: {session}')
            self.raw_data_folder = session
            self.jsonable_file = self.raw_data_folder.joinpath('_iblrig_taskData.raw.jsonable')
            self.settings_file = self.raw_data_folder.joinpath('_iblrig_taskSettings.raw.json')
            if not self.jsonable_file.exists():
                print('Waiting for data ...')
                while not self.jsonable_file.exists():
                    time.sleep(0.2)
            is_live = True

        # If session is a file ...
        elif session.is_file():
            if not session.name.endswith('.raw.jsonable'):
                raise ValueError(f'Not a Task Data File: {session}')
            self.jsonable_file = session
            self.raw_data_folder = session.parent
            self.settings_file = self.raw_data_folder.joinpath('_iblrig_taskSettings.raw.json')

        if self.settings_file.exists():
            with self.settings_file.open('r') as f:
                self.task_settings = json.load(f)
            self.probability_set = [self.task_settings.get('PROBABILITY_LEFT')] + self.task_settings.get(
                'BLOCK_PROBABILITY_SET', []
            )
            self.contrast_set = np.unique(np.abs(self.task_settings.get('CONTRAST_SET')))

        self.signed_contrasts = np.r_[-np.flipud(self.contrast_set[1:]), self.contrast_set]
        self.psychometrics = pd.DataFrame(
            columns=['count', 'response_time', 'choice', 'response_time_std', 'choice_std'],
            index=pd.MultiIndex.from_product([self.probability_set, self.signed_contrasts]),
        )
        self.psychometrics['count'] = 0
        self.reward_amount = 0
        self._t0 = 0
        self._n_trials = 0
        self._n_trials_correct = 0
        self._n_trials_engaged = 0
        self._seconds_elapsed = 0
        self.titleColor = ''

        # get session string in separate thread
        session_string_worker = Worker(self.getSessionString)
        QThreadPool.globalInstance().start(session_string_worker)

        # read the jsonable file and instantiate a QFileSystemWatcher
        self.readJsonable(self.jsonable_file)
        if is_live:
            self.jsonableWatcher = QFileSystemWatcher([str(self.jsonable_file)], parent=self)
            self.jsonableWatcher.fileChanged.connect(self.readJsonable)

    @Slot(str)
    def readJsonable(self, _: str) -> None:
        # load jsonable data
        trial_data, bpod_data = load_task_jsonable(self.jsonable_file, offset=self._jsonable_offset)
        self._jsonable_offset = self.jsonable_file.stat().st_size
        self._trial_data = pd.concat([self._trial_data, trial_data])
        if len(self._bpod_data) == 0:
            self._t0 = bpod_data[0]['Trial start timestamp']
        self._bpod_data.extend(bpod_data)

        # update data for trial history table
        table = self._trial_data[['trial_num', 'position', 'contrast']].copy()
        table.columns = ['Trial', 'Stimulus', 'Contrast']
        table['Debias'] = self._trial_data.get('debias_trial', False)
        table['Outcome'] = self._trial_data.apply(
            lambda row: 'no-go'
            if (row.get('response_side') == 0 or row.get('response_time') > 60)
            else ('correct' if row.get('trial_correct') else 'error'),
            axis=1,
        )
        table['Response Time / s'] = self._trial_data.apply(
            lambda row: np.NAN if row.get('response_side') == 0 else row.get('response_time'), axis=1
        )
        self.tableModel.setDataFrame(table)

        # update some counters
        self._n_trials += len(trial_data)
        if len(bpod_data) > 1:
            seconds_elapsed = np.array([trial['Trial end timestamp'] for trial in bpod_data]) - self._t0
            self._seconds_elapsed = seconds_elapsed[-1]
            self._n_trials_engaged += (seconds_elapsed <= EngagedCriterion.SECONDS).sum()
        else:
            self._seconds_elapsed = bpod_data[-1]['Trial end timestamp'] - self._t0
            self._n_trials_engaged += self._seconds_elapsed <= EngagedCriterion.SECONDS
        self._n_trials_correct += trial_data['trial_correct'].sum()
        self.reward_amount += trial_data['reward_amount'].sum()

        # update psychometrics
        trial_data['signed_contrast'] = np.sign(trial_data['position']) * trial_data['contrast']
        for _, row in trial_data.iterrows():
            if row.get('response_side') == 0:
                continue
            choice = row.position > 0 if row.trial_correct else row.position < 0
            indexer = (row.stim_probability_left, row.signed_contrast)
            if indexer not in self.psychometrics.index:
                self.psychometrics.loc[indexer, :] = np.nan
                self.psychometrics.loc[indexer, 'count'] = 0
            self.psychometrics.loc[indexer, 'count'] += 1
            self.psychometrics.loc[indexer, 'response_time'], self.psychometrics.loc[indexer, 'response_time_std'] = online_std(
                new_sample=row.response_time,
                new_count=self.psychometrics.loc[indexer, 'count'],
                old_mean=self.psychometrics.loc[indexer, 'response_time'],
                old_std=self.psychometrics.loc[indexer, 'response_time_std'],
            )
            self.psychometrics.loc[indexer, 'choice'], self.psychometrics.loc[indexer, 'choice_std'] = online_std(
                new_sample=float(choice),
                new_count=self.psychometrics.loc[indexer, 'count'],
                old_mean=self.psychometrics.loc[indexer, 'choice'],
                old_std=self.psychometrics.loc[indexer, 'choice_std'],
            )

        self.compute_end_session_criteria()
        self.setCurrentTrial(self._n_trials - 1)

    def compute_end_session_criteria(self):
        """Implement critera to change the color of the figure display, according to the specifications of the task."""
        # Within the first part of the session we don't apply response time criterion
        if self._seconds_elapsed < EngagedCriterion.SECONDS:
            color = Colors.TRANSPARENT

        # if the mouse has been training for more than 90 minutes subject training too long
        elif self._seconds_elapsed > (90 * 60):
            color = Colors.RED

        # the mouse fails to do more than 400 trials in the first 45 mins
        elif self._n_trials_engaged <= EngagedCriterion.TRIAL_COUNT:
            color = Colors.GREEN

        # the subject reaction time over the last 20 trials is more than 5 times greater than the overall reaction time
        elif (self._trial_data['response_time'].median() * 5) < self._trial_data['response_time'][-20:].median():
            color = Colors.YELLOW

        # 90 > time > 45 min and subject's avg response time hasn't significantly decreased
        else:
            color = Colors.TRANSPARENT

        if self.titleColor != color:
            self.titleColor = color
            self.titleColorChanged.emit(color)

    def getSessionString(self) -> None:
        if not hasattr(self, 'task_settings'):
            return
        training_info, _ = get_subject_training_info(
            subject_name=self.task_settings.get('SUBJECT_NAME'),
            task_name=self.task_settings.get('PYBPOD_PROTOCOL'),
            lab=self.task_settings.get('ALYX_LAB'),
        )
        use_adaptive_reward = self.task_settings.get('ADAPTIVE_REWARD', False)
        reward_amount = training_info['adaptive_reward'] if use_adaptive_reward else self.task_settings.get('REWARD_AMOUNT_UL')
        self.sessionString = (
            f'Subject: {self.task_settings.get("SUBJECT_NAME")}  ·  '
            f'Weight: {self.task_settings.get("SUBJECT_WEIGHT"):0.1f} g  ·  '
            f'Training Phase: {training_info["training_phase"]}  ·  '
            f'Stimulus Gain: {self.task_settings.get("STIM_GAIN"):0.1f}  ·  '
            f'{"Adaptive " if use_adaptive_reward else ""}Reward Amount: {reward_amount:0.1f} µl'
        )
        self.sessionStringAvailable.emit(self.sessionString)

    @Slot(int)
    def setCurrentTrial(self, value: int) -> None:
        if value != self._current_trial:
            self._current_trial = value
            self.currentTrialChanged.emit(value)
            self.titleChanged.emit(self.getTitle())

    def currentTrial(self) -> int:
        return self._current_trial

    def nTrials(self) -> int:
        return self._n_trials

    def timeElapsed(self) -> datetime.timedelta:
        if self._n_trials == 0:
            return datetime.timedelta(seconds=0)
        t1 = self._bpod_data[self._current_trial]['Trial end timestamp']
        return datetime.timedelta(seconds=t1 - self._t0)

    def percentCorrect(self) -> float:
        return self._n_trials_correct / (self._n_trials if self._n_trials > 0 else np.nan) * 100

    def bpod_data(self, trial: int) -> pd.DataFrame:
        return bpod_trial_data_to_dataframe(self._bpod_data[trial], trial)

    def getTitle(self) -> str:
        protocol = getattr(self, 'task_settings', dict()).get('PYBPOD_PROTOCOL', 'unknown task protocol')
        spacer = '  ·  '
        t_elapsed = str(self.timeElapsed()).split('.')[0]
        return f'{protocol}{spacer}Trial {self._current_trial}{spacer}Elapsed Time: {t_elapsed}'


class OnlinePlotsView(QMainWindow):
    colormap = pg.colormap.get('tab10', source='matplotlib')

    def __init__(self, session: FilePath | DirectoryPath | UUID4, parent: QObject | None = None):
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        self.model = OnlinePlotsModel(session, self)

        self.statusBar().clearMessage()
        self.setWindowTitle('Online Plots')
        self.setMinimumSize(1024, 771)
        self.setWindowIcon(QIcon(QPixmap(':/images/iblrig_logo')))

        # the frame that contains all the plots
        frame = QFrame(self)
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet('background-color: rgb(255, 255, 255);')
        self.setCentralWidget(frame)

        # use a grid layout to organize the different widgets
        layout = QGridLayout(frame)
        frame.setLayout(layout)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 2)

        # titles are arranged in a sub-layout to allow changing the background color in unison
        self.titleFrame = QFrame(self)
        title_layout = QVBoxLayout(self.titleFrame)
        self.titleFrame.setLayout(title_layout)
        layout.addWidget(self.titleFrame, 0, 0, 1, 3)

        # main title
        self.title = QLabel(self.model.getTitle(), self)
        self.title.setAlignment(Qt.AlignHCenter)
        font = self.title.font()
        font.setPointSize(15)
        font.setBold(True)
        self.title.setFont(font)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setTitleBackground(self.model.titleColor)
        title_layout.addWidget(self.title)

        # sub title
        self.subtitle = QLabel(self)
        self.model.sessionStringAvailable.connect(self.subtitle.setText)
        self.subtitle.setText(self.model.sessionString)
        self.subtitle.setAlignment(Qt.AlignHCenter)
        font.setPointSize(10)
        self.subtitle.setFont(font)
        self.subtitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        title_layout.addWidget(self.subtitle)

        # trial history
        self.trials = TrialsWidget(self, self.model.tableModel)
        self.trials.trialSelected.connect(self.model.setCurrentTrial)
        layout.addWidget(self.trials, 1, 0, 2, 1)

        # psychometric function
        self.psychometricWidget = FunctionWidget(parent=self, colors=self.colormap, probabilities=self.model.probability_set)
        self.psychometricWidget.plotItem.setTitle('Psychometric Function', color='k')
        self.psychometricWidget.plotItem.getAxis('left').setLabel('Rightward Choices (%)')
        self.psychometricWidget.plotItem.addItem(pg.InfiniteLine(0.5, 0, 'black'))
        self.psychometricWidget.plotItem.setYRange(0, 1, padding=0.05)
        self.psychometricWidget.plotItem.hoverEvent = self.mouseOverFunction
        layout.addWidget(self.psychometricWidget, 1, 1, 1, 1)

        # chronometric function
        self.chronometricWidget = FunctionWidget(parent=self, colors=self.colormap, probabilities=self.model.probability_set)
        self.chronometricWidget.plotItem.setTitle('Chronometric Function', color='k')
        self.chronometricWidget.plotItem.getAxis('left').setLabel('Response Time (s)')
        self.chronometricWidget.plotItem.setLogMode(x=False, y=True)
        self.chronometricWidget.plotItem.setXLink(self.psychometricWidget.plotItem)
        self.chronometricWidget.plotItem.setXRange(-1, 1, padding=0.025)
        self.chronometricWidget.plotItem.setYRange(-1, 2, padding=0.05)
        self.chronometricWidget.plotItem.hoverEvent = self.mouseOverFunction
        layout.addWidget(self.chronometricWidget, 2, 1, 1, 1)

        # performance chart
        self.performanceWidget = SingleBarChartWidget(parent=self, textFormat='{:0.1f} %')
        self.performanceWidget.setMinimumWidth(155)
        self.performanceWidget.plotItem.setTitle('Performance', color='k')
        self.performanceWidget.plotItem.getAxis('left').setLabel('Correct Choices (%)')
        self.performanceWidget.plotItem.setYRange(0, 105, padding=0)
        self.performanceWidget.plotItem.hoverEvent = self.mouseOverBarChart
        layout.addWidget(self.performanceWidget, 1, 2, 1, 1)

        # reward chart
        self.rewardWidget = SingleBarChartWidget(parent=self, barColor=(64, 64, 255), textFormat='{:0.1f} μl')
        self.rewardWidget.plotItem.setTitle('Reward Amount', color='k')
        self.rewardWidget.plotItem.getAxis('left').setLabel('Total Reward Volume (μl)')
        self.rewardWidget.plotItem.setYRange(0, 1050, padding=0)
        self.rewardWidget.plotItem.hoverEvent = self.mouseOverBarChart
        layout.addWidget(self.rewardWidget, 2, 2, 1, 1)

        # bpod data
        self.bpodWidget = BpodWidget(self, title='Bpod States and Input Channels')
        self.bpodWidget.setMinimumHeight(130)
        self.bpodWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(self.bpodWidget, 3, 0, 1, 3)

        # connect signals / slots
        self.model.titleChanged.connect(self.setTitle)
        self.model.titleColorChanged.connect(self.setTitleBackground)
        self.model.currentTrialChanged.connect(self.updatePlots)
        self.updatePlots(self.model.nTrials() - 1)

        # manage settings
        self.settings = QSettings()
        self.move(self.settings.value('pos', self.pos(), QPoint))
        self.resize(self.settings.value('size', self.size(), QSize))

    @Slot(str)
    def setTitle(self, title: str):
        self.title.setText(title)

    @Slot(str)
    def setTitleBackground(self, color: str):
        """Set the background color of the title area to a gradient of the specified color."""
        self.titleFrame.setStyleSheet(f'QFrame {{ background-color: {color}; }}')

    def mouseOverBarChart(self, event):
        statusbar = self.window().statusBar()
        if event.exit:
            statusbar.clearMessage()
        elif event.currentItem.vb.sceneBoundingRect().contains(event.scenePos()):
            if event.currentItem == self.performanceWidget.plotItem:
                statusbar.showMessage(f'Performance: {self.model.percentCorrect():0.1f}% correct choices')
            else:
                statusbar.showMessage(f'Total reward volume: {self.model.reward_amount:0.1f} μl')

    def mouseOverFunction(self, event):
        statusbar = self.window().statusBar()
        if event.exit:
            statusbar.clearMessage()
        elif event.currentItem.vb.sceneBoundingRect().contains(event.scenePos()):
            if event.currentItem == self.psychometricWidget.plotItem:
                statusbar.showMessage('Psychometric Function, SEM')
            else:
                statusbar.showMessage('Chronometric Function, SEM')

    @Slot(int)
    def updatePlots(self, trial: int):
        self.bpodWidget.setData(self.model.bpod_data(trial))
        self.trials.table_view.setCurrentIndex(self.model.tableModel.index(trial, 0))
        self.trials.table_view.scrollTo(self.model.tableModel.index(trial, 0))
        for p in self.model.probability_set:
            data = self.model.psychometrics.loc[p].dropna(axis=0).astype(float)
            x = data.index.to_numpy()
            y = data.choice.to_numpy()
            sqrt_n = np.sqrt(data['count'].to_numpy())
            e = data.choice_std.to_numpy() / sqrt_n
            self.psychometricWidget.upperCurves[p].setData(x=x, y=y + e)
            self.psychometricWidget.lowerCurves[p].setData(x=x, y=y - e)
            self.psychometricWidget.plotDataItems[p].setData(x=x, y=y)
            y = data.response_time.to_numpy()
            e = data.response_time_std.to_numpy() / sqrt_n
            self.chronometricWidget.upperCurves[p].setData(x=x, y=y + e)
            self.chronometricWidget.lowerCurves[p].setData(x=x, y=np.clip(y - e, np.finfo(float).tiny, None))
            self.chronometricWidget.plotDataItems[p].setData(x=x, y=y)
        self.performanceWidget.setValue(self.model.percentCorrect())
        self.rewardWidget.setValue(self.model.reward_amount)
        self.update()

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

    def moveEvent(self, event):
        if hasattr(self, 'settings'):
            self.settings.setValue('pos', self.pos())
        super().moveEvent(event)

    def resizeEvent(self, event):
        if hasattr(self, 'settings'):
            self.settings.setValue('size', self.size())
        super().resizeEvent(event)


def online_plots_cli(*args):
    sys.argv.extend([str(arg) for arg in args])

    class CLISettings(BaseSettings, cli_parse_args=True, cli_enforce_required=False, cli_avoid_json=True):
        """Display a Session's Online Plot."""

        session: CliPositionalArg[FilePath | DirectoryPath | UUID4] = Field(description="a session's Task Data File or eID")

    # set app information
    QCoreApplication.setOrganizationName('International Brain Laboratory')
    QCoreApplication.setOrganizationDomain('internationalbrainlab.org')
    QCoreApplication.setApplicationName('IBLRIG Online Plots')
    if os.name == 'nt':
        app_id = f'IBL.iblrig.online_plots.{iblrig_version}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication([])

    if len(sys.argv) < 2:
        local_subjects_folder = str(get_local_and_remote_paths()['local_subjects_folder'])
        session, _ = QFileDialog.getOpenFileName(
            caption='Select Task Data File', filter='Task Data (*.raw.jsonable)', directory=local_subjects_folder
        )
        if len(session) == 0:
            return
    else:
        session = CLISettings().session
    window = OnlinePlotsView(session)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    online_plots_cli()
