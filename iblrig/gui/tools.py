import argparse
import subprocess
import sys
import traceback
from collections.abc import Callable
from typing import Any

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal

from iblrig.constants import BASE_PATH


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
        filename_in = filename_in.relative_to(BASE_PATH)
        filename_out = filename_in.with_stem(filename_in.stem + '_rc').with_suffix('.py')
        print(filename_out)
        args = ['pyrcc5', str(filename_in), '-o', filename_out]
        subprocess.check_output(args, cwd=BASE_PATH)

    for filename_in in files.intersection(gui_path.glob('*.ui')):
        filename_in = filename_in.relative_to(BASE_PATH)
        filename_out = filename_in.with_suffix('.py')
        print(filename_out)
        args = ['pyuic5', str(filename_in), '-o', filename_out, '-x', '--import-from=iblrig.gui']
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
