import argparse
import subprocess
import sys
import traceback
from collections.abc import Callable
from inspect import signature
from pathlib import Path
from shutil import disk_usage
from typing import Any

import numpy as np
import pandas as pd
from PyQt5 import QtGui
from PyQt5.Qt import pyqtSlot
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QObject, QRunnable, Qt, QThreadPool, QVariant, pyqtProperty, pyqtSignal
from PyQt5.QtWidgets import QProgressBar, QLineEdit, QAction

from iblrig.constants import BASE_PATH
from iblutil.util import dir_size


def convert_uis():
    """
    A wrapper for PyQt5's pyuic5 and pyrcc5, set up for development on iblrig
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('pattern', nargs='?', default='*.*', type=str)
    args = parser.parse_args()

    gui_path = BASE_PATH.joinpath('iblrig', 'gui')
    files = set([f for f in gui_path.glob(args.pattern)])

    for filename_in in files.intersection(gui_path.glob('*.qrc')):
        rel_path_in = filename_in.relative_to(BASE_PATH)
        rel_path_out = rel_path_in.with_stem(rel_path_in.stem + '_rc').with_suffix('.py')
        args = ['pyrcc5', str(rel_path_in), '-o', str(rel_path_out)]
        print(' '.join(args))
        subprocess.check_output(args, cwd=BASE_PATH)

    for filename_in in files.intersection(gui_path.glob('*.ui')):
        rel_path_in = filename_in.relative_to(BASE_PATH)
        rel_path_out = rel_path_in.with_suffix('.py')
        args = ['pyuic5', str(rel_path_in), '-o', str(rel_path_out), '-x', '--import-from=iblrig.gui']
        print(' '.join(args))
        subprocess.check_output(args, cwd=BASE_PATH)


class WorkerSignals(QObject):
    """
    Signals used by the Worker class to communicate with the main thread.

    Attributes
    ----------
    finished : pyqtSignal
        Signal emitted when the worker has finished its task.

    error : pyqtSignal(tuple)
        Signal emitted when an error occurs. The signal carries a tuple with the exception type,
        exception value, and the formatted traceback.

    result : pyqtSignal(Any)
        Signal emitted when the worker has successfully completed its task. The signal carries
        the result of the task.

    progress : pyqtSignal(int)
        Signal emitted to report progress during the task. The signal carries an integer value.
    """

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class DiskSpaceIndicator(QProgressBar):
    """A custom progress bar widget that indicates the disk space usage of a specified directory."""

    def __init__(self, *args, directory: Path | None, percent_threshold: int = 90, **kwargs):
        """
        Initialize the DiskSpaceIndicator with the specified directory and threshold percentage.

        Parameters
        ----------
        *args : tuple
            Variable length argument list (passed to QProgressBar).
        directory : Path or None
            The directory path to monitor for disk space usage.
        percent_threshold : int, optional
            The threshold percentage at which the progress bar changes color to red. Default is 90.
        **kwargs : dict
            Arbitrary keyword arguments (passed to QProgressBar).
        """
        super().__init__(*args, **kwargs)
        self._directory = directory
        self._percent_threshold = percent_threshold
        self._percent_full = float('nan')
        self.setEnabled(False)
        if self._directory is not None:
            self.update_data()

    def update_data(self):
        """Update the disk space information."""
        worker = Worker(self._get_size)
        worker.signals.result.connect(self._on_get_size_result)
        QThreadPool.globalInstance().start(worker)

    @property
    def critical(self) -> bool:
        """True if the disk space usage is above the given threshold percentage."""
        return self._percent_full > self._percent_threshold

    def _get_size(self):
        """Get the disk usage information for the specified directory."""
        usage = disk_usage(self._directory.anchor)
        self._percent_full = usage.used / usage.total * 100
        self._gigs_dir = dir_size(self._directory) / 1024**3
        self._gigs_free = usage.free / 1024**3

    def _on_get_size_result(self, result):
        """Handle the result of getting disk usage information and update the progress bar accordingly."""
        self.setEnabled(True)
        self.setValue(round(self._percent_full))
        if self.critical:
            p = self.palette()
            p.setColor(QtGui.QPalette.Highlight, QtGui.QColor('red'))
            self.setPalette(p)
        self.setStatusTip(f'{self._directory}: {self._gigs_dir:.1f} GB  •  ' f'available space: {self._gigs_free:.1f} GB')


class Worker(QRunnable):
    """
    A generic worker class for executing functions concurrently in a separate thread.

    This class is designed to run functions concurrently in a separate thread and emit signals
    to communicate the results or errors back to the main thread.

    Adapted from: https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

    Attributes
    ----------
    fn : Callable
        The function to be executed concurrently.

    args : tuple
        Positional arguments for the function.

    kwargs : dict
        Keyword arguments for the function.

    signals : WorkerSignals
        An instance of WorkerSignals used to emit signals.

    Methods
    -------
    run() -> None
        The main entry point for running the worker. Executes the provided function and
        emits signals accordingly.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        """
        Initialize the Worker instance.

        Parameters
        ----------
        fn : Callable
            The function to be executed concurrently.

        *args : tuple
            Positional arguments for the function.

        **kwargs : dict
            Keyword arguments for the function.
        """
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals: WorkerSignals = WorkerSignals()
        if 'progress_callback' in signature(fn).parameters:
            self.kwargs['progress_callback'] = self.signals.progress

    def run(self) -> None:
        """
        Execute the provided function and emit signals accordingly.

        This method is the main entry point for running the worker. It executes the provided
        function and emits signals to communicate the results or errors back to the main thread.

        Returns
        -------
        None
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:  # noqa: E722
            # Handle exceptions and emit error signal with exception details
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Emit result signal with the result of the task
            self.signals.result.emit(result)
        finally:
            # Emit the finished signal to indicate completion
            self.signals.finished.emit()


class DataFrameTableModel(QAbstractTableModel):
    def __init__(self, *args, df: pd.DataFrame, **kwargs):
        super().__init__(*args, **kwargs)
        self._dataFrame = df

    def dataFrame(self):
        return self._dataFrame

    def setDataFrame(self, data_frame: pd.DataFrame):
        self.beginResetModel()
        self._dataFrame = data_frame.copy()
        self.endResetModel()

    dataFrame = pyqtProperty(pd.DataFrame, fget=dataFrame, fset=setDataFrame)

    def headerData(self, section, orientation, role=...):
        """
        Get the header data for the specified section.

        Parameters
        ----------
        section : int
            The section index.
        orientation : Qt.Orientation
            The orientation of the header.
        role : int, optional
            The role of the header data.

        Returns
        -------
        QVariant
            The header data.
        """
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._dataFrame.columns[section])
            else:
                return str(self._dataFrame.index[section])

    def rowCount(self, parent=...):
        """
        Get the number of rows in the model.

        Parameters
        ----------
        parent : QModelIndex, optional
            The parent index.

        Returns
        -------
        int
            The number of rows.
        """
        if isinstance(parent, QModelIndex) and parent.isValid():
            return 0
        return self.dataFrame.shape[0]

    def columnCount(self, parent=...):
        """
        Get the number of columns in the model.

        Parameters
        ----------
        parent : QModelIndex, optional
            The parent index.

        Returns
        -------
        int
            The number of columns.
        """
        if isinstance(parent, QModelIndex) and parent.isValid():
            return 0
        return self.dataFrame.shape[1]

    def data(self, index, role=...):
        """
        Get the data for the specified index.

        Parameters
        ----------
        index : QModelIndex
            The index of the data.
        role : int, optional
            The role of the data.

        Returns
        -------
        QVariant
            The data for the specified index.
        """
        if index.isValid():
            row = self._dataFrame.index[index.row()]
            col = self._dataFrame.columns[index.column()]
            dat = self._dataFrame.iloc[row][col]
            if role == Qt.DisplayRole:
                if isinstance(dat, np.generic):
                    return dat.item()
                return dat
        return QVariant()

    def sort(self, column, order=...):
        """
        Sort the data based on the specified column and order.

        Parameters
        ----------
        column : int
            The column index to sort by.
        order : Qt.SortOrder, optional
            The sort order.
        """
        self.layoutAboutToBeChanged.emit()
        col_name = self._dataFrame.columns.values[column]
        self._dataFrame.sort_values(by=col_name, ascending=order == Qt.AscendingOrder, inplace=True)
        self._dataFrame.reset_index(inplace=True, drop=True)
        self.layoutChanged.emit()

    def setData(self, index, value, role=Qt.DisplayRole):
        """
        Set data at the specified index with the given value.

        Parameters
        ----------
        index : QModelIndex
            The index where the data will be set.
        value : Any
            The new value to be set at the specified index.
        role : int, optional
            The role of the data. Default is Qt.DisplayRole.
        """
        if index.isValid():
            row = self._dataFrame.index[index.row()]
            col = self._dataFrame.columns[index.column()]
            self._dataFrame.at[row, col] = value
            self.dataChanged.emit(index, index, [role])


class LineEditAlyxUser(QLineEdit):
    loggedIn = pyqtSignal(str)
    loggedOut = pyqtSignal()


    def __init__(self, *args, alyxURL: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.logInAction = self.addAction(AlyxAction,
                                          self.ActionPosition.TrailingPosition)
        self.logInAction.setVisible(False)
        self.returnPressed.connect(self.logIn)

    @pyqtSlot()
    def logIn(self):
        print('log in')
        self.logInAction.setIcon(QtGui.QIcon(':/images/check'))
        self.setReadOnly(True)

    @pyqtSlot()
    def logOut(self):
        self.setText('')
        self.setReadOnly(False)
        self.logInAction.setIcon(QtGui.QIcon.isNull())
        pass

    @property
    def loggedIn(self) -> bool:
        return True


class AlyxAction(QAction):
    pass
