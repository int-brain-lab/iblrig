import argparse
import logging
import subprocess
from typing import Any

from qtpy.QtCore import QSettings, Qt, Slot
from qtpy.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QLabel, QLayout, QListView, QVBoxLayout, QWidget

from iblqt.widgets import SlideToggle
from iblrig.constants import BASE_PATH
from iblrig.gui import resources_rc  # noqa: F401
from iblrig.net import get_remote_devices
from iblrig.pydantic_definitions import RigSettings

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
            item.setToolTip(f'Remote Device "{device_name}" - {device_address}')
            item.setData(device_name, Qt.UserRole)
            self.appendRow(item)


class SettingsDialog(QDialog):
    def __init__(self, main_key: str, title: str = 'Settings', parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)

        self._main_key = main_key
        self._settings = QSettings()
        self._group_boxes: dict[str, QGroupBox] = {}
        self._new_values: dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.setLayout(layout)

        self._add_group('sync', 'Synchronization')
        self._add_setting(
            'sync',
            'toggle',
            'Allow changing MAIN_SYNC from GUI',
            False,
            'Allow toggling the MAIN_SYNC option from the lower left corner of the GUI. Only enable this if you intend to '
            'use your rig for, both, pure behavior experiments and experiments that involve multiple rig computers.',
        )
        self._add_setting(
            'sync',
            'warn',
            'Warn about MAIN_SYNC setting before starting session',
            False,
            'Display a dialog box with the current MAIN_SYNC setting prior to starting a session.',
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save_and_close)
        layout.addWidget(buttons)

    def _add_group(self, key: str, label: str) -> QGroupBox:
        if key in self._group_boxes:
            raise ValueError(f"A settings group with key '{key}' already exists")
        widget = QGroupBox(title=label, parent=self)
        layout = QFormLayout(widget)
        layout.setContentsMargins(10, 10, 10, 0)
        layout.setVerticalSpacing(0)
        widget.setLayout(layout)
        self.layout().addWidget(widget)
        self._group_boxes[key] = widget
        return widget

    def _add_setting(self, group_key: str, setting_key: str, label: str, default: Any, description: str | None = None) -> QWidget:
        if group_key not in self._group_boxes:
            raise ValueError(f"No settings group with key '{group_key}'")

        key = f'{self._main_key}/{group_key}/{setting_key}'
        value = self._settings.value(key, default, type(default))

        group_box = self._group_boxes[group_key]
        widget = SlideToggle(group_box)
        widget.setChecked(value)
        widget.toggled.connect(lambda v: self._new_values.update({key: v}))
        group_box.layout().addRow(widget, QLabel(label))

        if description is not None:
            label = QLabel(description)
            font = label.font()
            font.setPointSize(font.pointSize() - 1)
            font.setItalic(True)
            label.setFont(font)
            label.setWordWrap(True)
            label.setContentsMargins(0, 0, 0, 10)
            group_box.layout().addRow(None, label)

        return widget

    def _save_and_close(self):
        for key, value in self._new_values.items():
            self._settings.setValue(key, value)
        self.accept()
