import argparse
import logging
import subprocess
from pathlib import Path
from shutil import disk_usage

from qtpy.QtCore import (
    Qt,
    QThreadPool,
    Slot,
)
from qtpy.QtGui import QColor, QPalette, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import QListView, QProgressBar

from iblqt.core import Worker
from iblrig.constants import BASE_PATH
from iblrig.gui import resources_rc  # noqa: F401
from iblrig.net import get_remote_devices
from iblrig.pydantic_definitions import RigSettings
from iblutil.util import dir_size

log = logging.getLogger(__name__)


def convert_uis():
    """A wrapper for PyQt5's pyuic5 and pyrcc5, set up for development on iblrig."""
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
            p.setColor(QPalette.Highlight, QColor('red'))
            self.setPalette(p)
        self.setStatusTip(f'{self._directory}: {self._gigs_dir:.1f} GB  •  available space: {self._gigs_free:.1f} GB')


class RemoteDevicesListView(QListView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)  # needed for status tips

    def getDevices(self):
        out = []
        for idx in self.selectedIndexes():
            out.append(self.model().itemData(idx)[Qt.UserRole])
        return out


class RemoteDevicesItemModel(QStandardItemModel):
    def __init__(self, *args, iblrig_settings: RigSettings, **kwargs):
        super().__init__(*args, **kwargs)
        self.remote_devices = get_remote_devices(iblrig_settings=iblrig_settings)
        self.update()

    @Slot()
    def update(self):
        self.clear()
        for device_name, device_address in self.remote_devices.items():
            item = QStandardItem(device_name)
            item.setStatusTip(f'Remote Device "{device_name}" - {device_address}')
            item.setData(device_name, Qt.UserRole)
            self.appendRow(item)
