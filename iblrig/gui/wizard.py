import argparse
import ctypes
import datetime
import functools
import importlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import traceback
import webbrowser
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyqtgraph as pg
from pydantic import ValidationError
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets
from PyQt5.QtCore import QThread, QThreadPool
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWidgets import QStyle
from requests import HTTPError
from serial import SerialException

import iblrig.hardware_validation
import iblrig.path_helper
import iblrig_tasks
from iblrig.base_tasks import EmptySession, ValveMixin
from iblrig.choiceworld import get_subject_training_info, training_phase_from_contrast_set
from iblrig.constants import BASE_DIR
from iblrig.frame2ttl import Frame2TTL
from iblrig.gui.ui_frame2ttl import Ui_frame2ttl
from iblrig.gui.ui_login import Ui_login
from iblrig.gui.ui_update import Ui_update
from iblrig.gui.ui_valve import Ui_valve
from iblrig.gui.ui_wizard import Ui_wizard
from iblrig.hardware import Bpod
from iblrig.misc import _get_task_argument_parser
from iblrig.path_helper import load_pydantic_yaml, save_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings
from iblrig.scale import Scale
from iblrig.tools import alyx_reachable, get_anydesk_id, internet_available
from iblrig.valve import Valve
from iblrig.version_management import check_for_updates, get_changelog, is_dirty
from iblutil.util import Bunch, setup_logger
from one.webclient import AlyxClient
from pybpodapi.exceptions.bpod_error import BpodErrorException

try:
    import iblrig_custom_tasks

    CUSTOM_TASKS = True
except ImportError:
    CUSTOM_TASKS = False
    pass

log = logging.getLogger(__name__)
pg.setConfigOption('foreground', 'k')
pg.setConfigOptions(antialias=True)

PROCEDURES = [
    'Behavior training/tasks',
    'Ephys recording with acute probe(s)',
    'Ephys recording with chronic probe(s)',
    'Fiber photometry',
    'handling_habituation',
    'Imaging',
]
PROJECTS = ['ibl_neuropixel_brainwide_01', 'practice']

URL_DOC = 'https://int-brain-lab.github.io/iblrig'
URL_REPO = 'https://github.com/int-brain-lab/iblrig/tree/iblrigv8'
URL_ISSUES = 'https://github.com/int-brain-lab/iblrig/issues'
URL_DISCUSSION = 'https://github.com/int-brain-lab/iblrig/discussions'

ANSI_COLORS: dict[bytes, str] = {'31': 'Red', '32': 'Green', '33': 'Yellow', '35': 'Magenta', '36': 'Cyan', '37': 'White'}
REGEX_STDOUT = re.compile(
    r'^\x1b\[(?:\d;)?(?:\d+;)?'
    r'(?P<color>\d+)m[\d-]*\s+'
    r'(?P<time>[\d\:]+)\s+'
    r'(?P<level>\w+\s+)'
    r'(?P<file>[\w\:\.]+)\s+'
    r'(?P<message>[^\x1b]*)',
    re.MULTILINE,
)


def _set_list_view_from_string_list(ui_list: QtWidgets.QListView, string_list: list):
    """Small boiler plate util to set the selection of a list view from a list of strings"""
    if string_list is None or len(string_list) == 0:
        return
    for i, s in enumerate(ui_list.model().stringList()):
        if s in string_list:
            ui_list.selectionModel().select(ui_list.model().createIndex(i, 0), QtCore.QItemSelectionModel.Select)


@dataclass
class RigWizardModel:
    alyx: AlyxClient | None = None
    procedures: list | None = None
    projects: list | None = None
    task_name: str | None = None
    user: str | None = None
    subject: str | None = None
    session_folder: Path | None = None
    test_subject_name = 'test_subject'
    subject_details_worker = None
    subject_details: tuple | None = None
    free_reward_time: float | None = None
    file_iblrig_settings: Path | str | None = None
    file_hardware_settings: Path | str | None = None

    def __post_init__(self):
        self.iblrig_settings: RigSettings = load_pydantic_yaml(RigSettings, filename=self.file_iblrig_settings, do_raise=True)
        self.hardware_settings: HardwareSettings = load_pydantic_yaml(
            HardwareSettings, filename=self.file_hardware_settings, do_raise=True
        )

        # calculate free reward time
        class FakeSession(ValveMixin):
            hardware_settings = self.hardware_settings
            task_params = Bunch({'AUTOMATIC_CALIBRATION': True, 'REWARD_AMOUNT_UL': 10})

        fake_session = FakeSession()
        fake_session.init_mixin_valve()
        self.free_reward_time = fake_session.compute_reward_time(self.hardware_settings.device_valve.FREE_REWARD_VOLUME_UL)

        if self.iblrig_settings.ALYX_URL is not None:
            self.alyx = AlyxClient(base_url=str(self.iblrig_settings.ALYX_URL), silent=True)

        self.all_users = [self.iblrig_settings['ALYX_USER']] if self.iblrig_settings['ALYX_USER'] else []
        self.all_procedures = sorted(PROCEDURES)
        self.all_projects = sorted(PROJECTS)

        # for the tasks, we build a dictionary that contains the task name as key and the path to task.py as value
        tasks = sorted([p for p in Path(iblrig_tasks.__file__).parent.rglob('task.py')])
        if CUSTOM_TASKS:
            tasks.extend(sorted([p for p in Path(iblrig_custom_tasks.__file__).parent.rglob('task.py')]))
        self.all_tasks = OrderedDict({p.parts[-2]: p for p in tasks})

        # get the subjects from iterating over folders in the the iblrig data path
        if self.iblrig_settings['iblrig_local_data_path'] is None:
            self.all_subjects = [self.test_subject_name]
        else:
            folder_subjects = Path(self.iblrig_settings['iblrig_local_data_path']).joinpath(
                self.iblrig_settings['ALYX_LAB'], 'Subjects'
            )
            self.all_subjects = [self.test_subject_name] + sorted(
                [f.name for f in folder_subjects.glob('*') if f.is_dir() and f.name != self.test_subject_name]
            )

    def get_task_extra_parser(self, task_name=None):
        """
        Get the extra kwargs from the task, by importing the task and parsing the extra_parser static method
        This parser will give us a list of arguments and their types so we can build a custom dialog for this task
        :return:
        """
        assert task_name
        spec = importlib.util.spec_from_file_location('task', self.all_tasks[task_name])
        task = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = task
        spec.loader.exec_module(task)
        return task.Session.extra_parser()

    def login(
        self,
        username: str,
        password: str | None = None,
        do_cache: bool = False,
        alyx_client: AlyxClient | None = None,
        gui: bool = False,
    ) -> bool:
        # Use predefined AlyxClient for testing purposes:
        if alyx_client is not None:
            self.alyx = alyx_client

        # Alternatively, try to log in:
        else:
            try:
                self.alyx.authenticate(username, password, do_cache, force=password is not None)
                if self.alyx.is_logged_in and self.alyx.user == username:
                    self.user = self.alyx.user
                    log.info(f'Logged into {self.alyx.base_url} as {self.alyx.user}')
                else:
                    return False
            except HTTPError as e:
                if e.errno == 400 and any(x in e.response.text for x in ('credentials', 'required')):
                    log.error(e.filename)
                    return False
                else:
                    raise e

        # since we are connecting to Alyx, validate some parameters to ensure a smooth extraction
        result = iblrig.hardware_validation.ValidateAlyxLabLocation().run(self.alyx)
        if result.status == 'FAIL' and gui:
            QtWidgets.QMessageBox().critical(None, 'Error', f'{result.message}\n\n{result.solution}')

        # get subjects from Alyx: this is the set of subjects that are alive and not stock in the lab defined in settings
        rest_subjects = self.alyx.rest('subjects', 'list', alive=True, stock=False, lab=self.iblrig_settings['ALYX_LAB'])
        self.all_subjects.remove(self.test_subject_name)
        self.all_subjects = [self.test_subject_name] + sorted(set(self.all_subjects + [s['nickname'] for s in rest_subjects]))

        # then get the projects that map to the current user
        rest_projects = self.alyx.rest('projects', 'list')
        projects = [p['name'] for p in rest_projects if (username in p['users'] or len(p['users']) == 0)]
        self.all_projects = sorted(set(projects + self.all_projects))

        return True

    def logout(self):
        if not self.alyx.is_logged_in or self.alyx.user is not self.user:
            return
        log.info(f'User {self.user} logged out')
        self.alyx.logout()
        self.user = None
        self.__post_init__()

    def free_reward(self):
        try:
            bpod = Bpod(
                self.hardware_settings['device_bpod']['COM_BPOD'],
                skip_initialization=True,
                disable_behavior_ports=[1, 2, 3],
            )
            bpod.pulse_valve(open_time_s=self.free_reward_time)
        except (OSError, BpodErrorException):
            log.error('Cannot find bpod - is it connected?')
            return

    def get_subject_details(self, subject):
        self.subject_details_worker = SubjectDetailsWorker(subject)
        self.subject_details_worker.finished.connect(self.process_subject_details)
        self.subject_details_worker.start()

    def process_subject_details(self):
        self.subject_details = SubjectDetailsWorker.result


class RigWizard(QtWidgets.QMainWindow, Ui_wizard):
    def __init__(self, **kwargs):
        super().__init__()
        self.setupUi(self)

        self.debug = kwargs.get('debug', False)
        self.settings = QtCore.QSettings()
        self.move(self.settings.value('pos', self.pos(), QtCore.QPoint))

        try:
            self.model = RigWizardModel()
        except ValidationError as e:
            yml = (
                'hardware_settings.yaml'
                if 'hardware' in e.title
                else 'iblrig_settings.yaml'
                if 'iblrig' in e.title
                else 'Settings File'
            )
            loc = '.'.join(e.errors()[0]['loc'])
            msg = e.errors()[0]['msg']
            self._show_error_dialog(title=f'Error validating {yml}', description=f'{loc}:\n{msg}.')
            raise e
        self.model2view()

        # default to biasedChoiceWorld
        if (idx := self.uiComboTask.findText('_iblrig_tasks_biasedChoiceWorld')) >= 0:
            self.uiComboTask.setCurrentIndex(idx)

        # connect widgets signals to slots
        self.uiActionTrainingLevelV7.triggered.connect(self._on_menu_training_level_v7)
        self.uiActionCalibrateFrame2ttl.triggered.connect(self._on_calibrate_frame2ttl)
        self.uiActionCalibrateValve.triggered.connect(self._on_calibrate_valve)
        self.uiComboTask.currentTextChanged.connect(self.controls_for_extra_parameters)
        self.uiComboSubject.currentTextChanged.connect(self.model.get_subject_details)
        self.uiPushStart.clicked.connect(self.start_stop)
        self.uiPushPause.clicked.connect(self.pause)
        self.uiListProjects.clicked.connect(self._enable_ui_elements)
        self.uiListProcedures.clicked.connect(self._enable_ui_elements)
        self.lineEditSubject.textChanged.connect(self._filter_subjects)

        self.running_task_process = None
        self.task_arguments = dict()
        self.task_settings_widgets = None

        self.uiPushStart.installEventFilter(self)
        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.uiPushPause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

        self.controller2model()

        self.tabWidget.currentChanged.connect(self._on_switch_tab)

        # username
        if self.model.iblrig_settings.ALYX_URL is not None:
            self.uiLineEditUser.returnPressed.connect(lambda w=self.uiLineEditUser: self._log_in_or_out(username=w.text()))
            self.uiPushButtonLogIn.released.connect(lambda w=self.uiLineEditUser: self._log_in_or_out(username=w.text()))
        else:
            self.uiLineEditUser.setPlaceholderText('')
            self.uiPushButtonLogIn.setEnabled(False)

        # tools
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushReward.clicked.connect(self.model.free_reward)
        self.uiPushReward.setStatusTip(
            f'Click to grant a free reward ({self.model.hardware_settings.device_valve.FREE_REWARD_VOLUME_UL:.1f} μL)'
        )
        self.uiPushStatusLED.setChecked(self.settings.value('bpod_status_led', True, bool))
        self.uiPushStatusLED.toggled.connect(self.toggle_status_led)
        self.toggle_status_led(self.uiPushStatusLED.isChecked())

        # tab: log
        font = QtGui.QFont('Monospace')
        font.setStyleHint(QtGui.QFont.TypeWriter)
        font.setPointSize(9)
        self.uiPlainTextEditLog.setFont(font)

        # tab: documentation
        self.uiPushWebHome.clicked.connect(lambda: self.webEngineView.load(QtCore.QUrl(URL_DOC)))
        self.uiPushWebBrowser.clicked.connect(lambda: webbrowser.open(str(self.webEngineView.url().url())))
        self.webEngineView.setPage(CustomWebEnginePage(self))
        self.webEngineView.setUrl(QtCore.QUrl(URL_DOC))
        self.webEngineView.urlChanged.connect(self._on_doc_url_changed)

        # tab: about
        self.uiLabelCopyright.setText(f'**IBLRIG v{iblrig.__version__}**\n\n© 2024, International Brain Laboratory')
        self.commandLinkButtonGitHub.clicked.connect(lambda: webbrowser.open(URL_REPO))
        self.commandLinkButtonDoc.clicked.connect(lambda: webbrowser.open(URL_DOC))
        self.commandLinkButtonIssues.clicked.connect(lambda: webbrowser.open(URL_ISSUES))
        self.commandLinkButtonDiscussion.clicked.connect(lambda: webbrowser.open(URL_DISCUSSION))

        # disk stats
        local_data = self.model.iblrig_settings['iblrig_local_data_path']
        local_data = Path(local_data) if local_data else Path.home().joinpath('iblrig_data')
        v8data_size = sum(file.stat().st_size for file in Path(local_data).rglob('*'))
        total_space, total_used, total_free = shutil.disk_usage(local_data.anchor)
        self.uiProgressDiskSpace = QtWidgets.QProgressBar(self)
        self.uiProgressDiskSpace.setMaximumWidth(70)
        self.uiProgressDiskSpace.setValue(round(total_used / total_space * 100))
        self.uiProgressDiskSpace.setStatusTip(
            f'local IBLRIG data: {v8data_size / 1024 ** 3 : .1f} GB  •  ' f'available space: {total_free / 1024 ** 3 : .1f} GB'
        )
        if self.uiProgressDiskSpace.value() > 90:
            p = self.uiProgressDiskSpace.palette()
            p.setColor(QtGui.QPalette.Highlight, QtGui.QColor('red'))
            self.uiProgressDiskSpace.setPalette(p)

        # statusbar
        self.statusbar.setContentsMargins(0, 0, 6, 0)
        self.statusbar.addPermanentWidget(self.uiProgressDiskSpace)
        self.controls_for_extra_parameters()

        # self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowFullscreenButtonHint)

        # disable control of LED if Bpod does not have the respective capability
        bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'], skip_initialization=True)
        self.uiPushStatusLED.setEnabled(bpod.can_control_led)

        # get AnyDesk ID
        anydesk_worker = Worker(get_anydesk_id, True)
        anydesk_worker.signals.result.connect(self._on_get_anydesk_result)
        QThreadPool.globalInstance().tryStart(anydesk_worker)

        # check for update
        update_worker = Worker(check_for_updates)
        update_worker.signals.result.connect(self._on_check_update_result)
        QThreadPool.globalInstance().start(update_worker)

        # check dirty state
        dirty_worker = Worker(is_dirty)
        dirty_worker.signals.result.connect(self._on_check_dirty_result)
        QThreadPool.globalInstance().start(dirty_worker)

    def _show_error_dialog(
        self,
        title: str,
        description: str,
        issues: list[str] | None = None,
        suggestions: list[str] | None = None,
        leads: list[str] | None = None,
    ):
        text = description.strip()

        def build_list(items: list[str] or None, header_singular: str, header_plural: str | None = None):
            nonlocal text
            if items is None or len(items) == 0:
                return
            if len(items) > 1:
                if header_plural is None:
                    header_plural = header_singular.strip() + 's'
                text += f'<br><br>{header_plural}:<ul>'
            else:
                text += f'<br><br>{header_singular.strip()}:<ul>'
            for item in items:
                text += f'<li>{item.strip()}</li>'
            text += '</ul>'

        build_list(issues, 'Possible issue')
        build_list(suggestions, 'Suggested action')
        build_list(leads, 'Possible lead')
        QtWidgets.QMessageBox.critical(self, title, text)

    def _on_switch_tab(self, index):
        # if self.tabWidget.tabText(index) == 'Session':
        # QtCore.QTimer.singleShot(1, lambda: self.resize(self.minimumSizeHint()))
        # self.adjustSize()
        pass

    def _on_menu_training_level_v7(self) -> None:
        """
        Prompt user for a session path to get v7 training level.

        This code will be removed and is here only for convenience while users transition from v7 to v8
        """
        if not (local_path := Path(r'C:\iblrig_data\Subjects')).exists():
            local_path = self.model.iblrig_settings['iblrig_local_data_path']
        session_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Session Path', str(local_path), QtWidgets.QFileDialog.ShowDirsOnly
        )
        if session_path is None or session_path == '':
            return
        file_jsonable = next(Path(session_path).glob('raw_behavior_data/_iblrig_taskData.raw.jsonable'), None)
        if file_jsonable is None:
            QtWidgets.QMessageBox().critical(self, 'Error', f'No jsonable found in {session_path}')
            return
        trials_table, _ = iblrig.raw_data_loaders.load_task_jsonable(file_jsonable)
        if trials_table.empty:
            QtWidgets.QMessageBox().critical(self, 'Error', f'No trials found in {session_path}')
            return

        last_trial = trials_table.iloc[-1]
        training_phase = training_phase_from_contrast_set(last_trial['contrast_set'])
        reward_amount = last_trial['reward_amount']
        stim_gain = last_trial['stim_gain']

        box = QtWidgets.QMessageBox(parent=self)
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setModal(False)
        box.setWindowTitle('Training Level')
        box.setText(
            f'{session_path}\n\n'
            f'training phase:\t{training_phase}\n'
            f'reward:\t{reward_amount} uL\n'
            f'stimulus gain:\t{stim_gain}'
        )
        if self.uiComboTask.currentText() == '_iblrig_tasks_trainingChoiceWorld':
            box.setStandardButtons(QtWidgets.QMessageBox.Apply | QtWidgets.QMessageBox.Close)
        else:
            box.setStandardButtons(QtWidgets.QMessageBox.Close)
        box.exec()
        if box.clickedButton() == box.button(QtWidgets.QMessageBox.Apply):
            self.uiGroupTaskParameters.findChild(QtWidgets.QWidget, '--adaptive_gain').setValue(stim_gain)
            self.uiGroupTaskParameters.findChild(QtWidgets.QWidget, '--adaptive_reward').setValue(reward_amount)
            self.uiGroupTaskParameters.findChild(QtWidgets.QWidget, '--training_phase').setValue(training_phase)

    def _on_calibrate_frame2ttl(self) -> None:
        Frame2TTLCalibrationDialog(self)

    def _on_calibrate_valve(self) -> None:
        ValveCalibrationDialog(self)

    def _on_check_update_result(self, result: tuple[bool, str]) -> None:
        """
        Handle the result of checking for updates.

        Parameters
        ----------
        result : tuple[bool, str | None]
            A tuple containing a boolean flag indicating update availability (result[0])
            and the remote version string (result[1]).

        Returns
        -------
        None
        """
        if result[0]:
            UpdateNotice(parent=self, version=result[1])

    def _on_get_anydesk_result(self, result: str | None) -> None:
        """
        Handle the result of checking for the user's AnyDesk ID.

        Parameters
        ----------
        result : str | None
            The user's AnyDesk ID, if available.

        Returns
        -------
        None
        """
        if result is not None:
            self.uiLabelAnyDesk.setText(f'Your AnyDesk ID: {result}')

    def _on_doc_url_changed(self):
        self.uiPushWebBack.setEnabled(len(self.webEngineView.history().backItems(1)) > 0)
        self.uiPushWebForward.setEnabled(len(self.webEngineView.history().forwardItems(1)) > 0)

    def _on_check_dirty_result(self, repository_is_dirty: bool) -> None:
        """
        Handle the result of checking for local changes in the repository.

        Parameters
        ----------
        repository_is_dirty : bool
            A boolean flag indicating whether the repository contains local changes.

        Returns
        -------
        None
        """
        if repository_is_dirty:
            msg_box = QtWidgets.QMessageBox(parent=self)
            msg_box.setWindowTitle('Warning')
            msg_box.setIcon(QtWidgets.QMessageBox().Warning)
            msg_box.setText("Your copy of iblrig contains local changes.\nDon't expect things to work as intended!")
            msg_box.setDetailedText(
                'To list all files that have been changed locally:\n\n'
                '    git diff --name-only\n\n'
                'To reset the repository to its default state:\n\n'
                '    git reset --hard'
            )
            msg_box.exec()

    def _log_in_or_out(self, username: str) -> bool:
        # Routine for logging out:
        if self.uiPushButtonLogIn.text() == 'Log Out':
            self.model.logout()
            self.uiLineEditUser.setText('')
            self.uiLineEditUser.setReadOnly(False)
            for action in self.uiLineEditUser.actions():
                self.uiLineEditUser.removeAction(action)
            self.uiLineEditUser.setStyleSheet('')
            self.uiLineEditUser.actions()
            self.uiPushButtonLogIn.setText('Log In')
            return True

        # Routine for logging in:
        # 1) Try to log in with just the username. This will succeed if the credentials for the respective user are cached. We
        #    also try to catch connection issues and show helpful error messages.
        try:
            logged_in = self.model.login(username, gui=True)
        except ConnectionError:
            if not internet_available(timeout=1, force_update=True):
                self._show_error_dialog(
                    title='Error connecting to Alyx',
                    description='Your computer appears to be offline.',
                    suggestions=['Check your internet connection.'],
                )
            elif not alyx_reachable():
                self._show_error_dialog(
                    title='Error connecting to Alyx',
                    description=f'Cannot connect to {self.model.iblrig_settings.ALYX_URL}',
                    leads=[
                        'Is `ALYX_URL` in `iblrig_settings.yaml` set correctly?',
                        'Is your machine allowed to connect to Alyx?',
                        'Is the Alyx server up and running nominally?',
                    ],
                )
            return False

        # 2) If there is no cached session for the given user and we can connect to Alyx: show the password dialog and loop
        #    until, either, the login was successful or the cancel button was pressed.
        if not logged_in:
            password = ''
            remember = False
            while not logged_in:
                dlg = LoginWindow(parent=self, username=username, password=password, remember=remember)
                if dlg.result():
                    username = dlg.lineEditUsername.text()
                    password = dlg.lineEditPassword.text()
                    remember = dlg.checkBoxRememberMe.isChecked()
                    dlg.deleteLater()
                    logged_in = self.model.login(username=username, password=password, do_cache=remember, gui=True)
                else:
                    dlg.deleteLater()
                    break

        # 3) Finally, if the login was successful, we need to apply some changes to the GUI
        if logged_in:
            self.uiLineEditUser.addAction(QtGui.QIcon(':/images/check'), QtWidgets.QLineEdit.ActionPosition.TrailingPosition)
            self.uiLineEditUser.setText(username)
            self.uiLineEditUser.setReadOnly(True)
            self.uiLineEditUser.setStyleSheet('background-color: rgb(246, 245, 244);')
            self.uiPushButtonLogIn.setText('Log Out')
            self.model2view()
        return logged_in

    def eventFilter(self, obj, event):
        if obj == self.uiPushStart and event.type() in [QtCore.QEvent.HoverEnter, QtCore.QEvent.HoverLeave]:
            for widget in [self.uiListProcedures, self.uiListProjects]:
                if len(widget.selectedIndexes()) > 0:
                    continue
                match event.type():
                    case QtCore.QEvent.HoverEnter:
                        widget.setStyleSheet('QListView { background-color: pink; border: 1px solid red; }')
                    case _:
                        widget.setStyleSheet('')
            return True
        return False

    def closeEvent(self, event) -> None:
        def accept() -> None:
            self.settings.setValue('pos', self.pos())
            self.settings.setValue('bpod_status_led', self.uiPushStatusLED.isChecked())
            self.toggle_status_led(is_toggled=True)
            bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])  # bpod is a singleton
            bpod.close()
            event.accept()

        if self.running_task_process is None:
            accept()
        else:
            msg_box = QtWidgets.QMessageBox(parent=self)
            msg_box.setWindowTitle('Hold on')
            msg_box.setText('A task is running - do you really want to quit?')
            msg_box.setStandardButtons(QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes)
            msg_box.setIcon(QtWidgets.QMessageBox().Question)
            match msg_box.exec_():
                case QtWidgets.QMessageBox.No:
                    event.ignore()
                case QtWidgets.QMessageBox.Yes:
                    self.setEnabled(False)
                    self.repaint()
                    self.start_stop()
                    accept()

    def model2view(self):
        # stores the current values in the model
        self.controller2model()
        # set the default values
        self.uiComboTask.setModel(QtCore.QStringListModel(list(self.model.all_tasks.keys())))
        self.uiComboSubject.setModel(QtCore.QStringListModel(self.model.all_subjects))
        self.uiListProcedures.setModel(QtCore.QStringListModel(self.model.all_procedures))
        self.uiListProjects.setModel(QtCore.QStringListModel(self.model.all_projects))
        # set the selections
        self.uiComboTask.setCurrentText(self.model.task_name)
        self.uiComboSubject.setCurrentText(self.model.subject)
        _set_list_view_from_string_list(self.uiListProcedures, self.model.procedures)
        _set_list_view_from_string_list(self.uiListProjects, self.model.projects)
        self._enable_ui_elements()

    def controller2model(self):
        self.model.procedures = [i.data() for i in self.uiListProcedures.selectedIndexes()]
        self.model.projects = [i.data() for i in self.uiListProjects.selectedIndexes()]
        self.model.task_name = self.uiComboTask.currentText()
        self.model.subject = self.uiComboSubject.currentText()

    def controls_for_extra_parameters(self):
        self.controller2model()
        self.task_arguments = dict()

        # collect & filter list of parser arguments (general & task specific)
        args = sorted(_get_task_argument_parser()._actions, key=lambda x: x.dest)
        args = [
            x
            for x in args
            if not any(
                set(x.option_strings).intersection(
                    [
                        '--subject',
                        '--user',
                        '--projects',
                        '--log-level',
                        '--procedures',
                        '--weight',
                        '--help',
                        '--append',
                        '--no-interactive',
                        '--stub',
                        '--wizard',
                    ]
                )
            )
        ]
        args = sorted(self.model.get_task_extra_parser(self.model.task_name)._actions, key=lambda x: x.dest) + args

        group = self.uiGroupTaskParameters
        layout = group.layout()
        self.task_settings_widgets = [None] * len(args)

        while layout.rowCount():
            layout.removeRow(0)

        for arg in args:
            param = max(arg.option_strings, key=len)
            label = param.replace('_', ' ').replace('--', '').title()

            # create widget for bool arguments
            if isinstance(arg, argparse._StoreTrueAction | argparse._StoreFalseAction):
                widget = QtWidgets.QCheckBox()
                widget.setTristate(False)
                if arg.default:
                    widget.setCheckState(arg.default * 2)
                widget.toggled.connect(lambda val, p=param: self._set_task_arg(p, val > 0))
                widget.toggled.emit(widget.isChecked() > 0)

            # create widget for string arguments
            elif arg.type in (str, None):
                if isinstance(arg.choices, list):
                    widget = QtWidgets.QComboBox()
                    widget.addItems(arg.choices)
                    if arg.default:
                        widget.setCurrentIndex([widget.itemText(x) for x in range(widget.count())].index(arg.default))
                    widget.currentTextChanged.connect(lambda val, p=param: self._set_task_arg(p, val))
                    widget.currentTextChanged.emit(widget.currentText())

                else:
                    widget = QtWidgets.QLineEdit()
                    if arg.default:
                        widget.setText(arg.default)
                    widget.editingFinished.connect(lambda p=param, w=widget: self._set_task_arg(p, w.text()))
                    widget.editingFinished.emit()

            # create widget for list of floats
            elif arg.type == float and arg.nargs == '+':
                widget = QtWidgets.QLineEdit()
                if arg.default:
                    widget.setText(str(arg.default)[1:-1])
                widget.editingFinished.connect(
                    lambda p=param, w=widget: self._set_task_arg(p, [x.strip() for x in w.text().split(',')])
                )
                widget.editingFinished.emit()

            # create widget for numerical arguments
            elif arg.type in [float, int]:
                if arg.type == float:
                    widget = QtWidgets.QDoubleSpinBox()
                    widget.setDecimals(1)
                else:
                    widget = QtWidgets.QSpinBox()
                if arg.default:
                    widget.setValue(arg.default)
                widget.valueChanged.connect(lambda val, p=param: self._set_task_arg(p, str(val)))
                widget.valueChanged.emit(widget.value())

            # no other argument types supported for now
            else:
                continue

            # add custom widget properties
            widget.setObjectName(param)
            widget.setProperty('parameter_name', param)
            widget.setProperty('parameter_dest', arg.dest)

            # display help strings as status tip
            if arg.help:
                widget.setStatusTip(arg.help)

            # some customizations
            match widget.property('parameter_dest'):
                case 'probability_left':
                    widget.setMinimum(0.0)
                    widget.setMaximum(1.0)
                    widget.setSingleStep(0.1)
                    widget.setDecimals(2)

                case 'contrast_set_probability_type':
                    label = 'Probability Type'

                case 'session_template_id':
                    label = 'Session Template ID'

                case 'delay_secs':
                    label = 'Initial Delay, s'

                case 'training_phase':
                    widget.setSpecialValueText('automatic')
                    widget.setMaximum(5)
                    widget.setMinimum(-1)
                    widget.setValue(-1)

                case 'adaptive_reward':
                    label = 'Reward Amount, μl'
                    widget.setSpecialValueText('automatic')
                    widget.setMaximum(3)
                    widget.setSingleStep(0.1)
                    widget.setMinimum(1.4)
                    widget.setValue(widget.minimum())
                    widget.valueChanged.connect(
                        lambda val, a=arg, m=widget.minimum(): self._set_task_arg(
                            a.option_strings[0], str(val if val > m else -1)
                        )
                    )
                    widget.valueChanged.emit(widget.value())

                case 'adaptive_gain':
                    label = 'Stimulus Gain'
                    widget.setSpecialValueText('automatic')
                    widget.setSingleStep(0.1)
                    widget.setMinimum(0)
                    widget.setValue(widget.minimum())
                    widget.valueChanged.connect(
                        lambda val, a=arg, m=widget.minimum(): self._set_task_arg(
                            a.option_strings[0], str(val if val > m else -1)
                        )
                    )
                    widget.valueChanged.emit(widget.value())

                case 'reward_amount_ul':
                    label = 'Reward Amount, μl'
                    widget.setSingleStep(0.1)
                    widget.setMinimum(0)

                case 'stim_gain':
                    label = 'Stimulus Gain'

            widget.wheelEvent = lambda event: None
            layout.addRow(self.tr(label), widget)

        # add label to indicate absence of task specific parameters
        if layout.rowCount() == 0:
            layout.addRow(self.tr('(none)'), None)
            layout.itemAt(0, 0).widget().setEnabled(False)

        # call timer to resize window
        QtCore.QTimer.singleShot(1, lambda: self.resize(self.minimumSizeHint()))

    def _set_task_arg(self, key, value):
        self.task_arguments[key] = value

    def alyx_connect(self):
        self.model.connect(gui=True)
        self.model2view()

    def _filter_subjects(self):
        filter_str = self.lineEditSubject.text().lower()
        result = [s for s in self.model.all_subjects if filter_str in s.lower()]
        if len(result) == 0:
            result = [self.model.test_subject_name]
        self.uiComboSubject.setModel(QtCore.QStringListModel(result))

    def pause(self):
        self.uiPushPause.setStyleSheet('QPushButton {background-color: yellow;}' if self.uiPushPause.isChecked() else '')
        match self.uiPushPause.isChecked():
            case True:
                print('Pausing after current trial ...')
                if self.model.session_folder.exists():
                    self.model.session_folder.joinpath('.pause').touch()
            case False:
                print('Resuming ...')
                if self.model.session_folder.joinpath('.pause').exists():
                    self.model.session_folder.joinpath('.pause').unlink()

    def start_stop(self):
        match self.uiPushStart.text():
            case 'Start':
                self.uiPushStart.setText('Stop')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
                self._enable_ui_elements()

                dlg = QtWidgets.QInputDialog()
                weight, ok = dlg.getDouble(
                    self,
                    'Subject Weight',
                    'Subject Weight (g):',
                    value=0,
                    min=0,
                    flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint,
                )
                if not ok or weight == 0:
                    self.uiPushStart.setText('Start')
                    self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                    self._enable_ui_elements()
                    return

                self.controller2model()
                task = EmptySession(subject=self.model.subject, append=self.uiCheckAppend.isChecked(), interactive=False)
                self.model.session_folder = task.paths['SESSION_FOLDER']
                if self.model.session_folder.joinpath('.stop').exists():
                    self.model.session_folder.joinpath('.stop').unlink()
                self.model.raw_data_folder = task.paths['SESSION_RAW_DATA_FOLDER']

                # disable Bpod status LED
                bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])
                bpod.set_status_led(False)

                # close Bpod singleton so subprocess can access use the port
                bpod.close()

                # runs the python command
                # cmd = [shutil.which('python')]
                cmd = []
                if self.model.task_name:
                    cmd.extend([str(self.model.all_tasks[self.model.task_name])])
                if self.model.user:
                    cmd.extend(['--user', self.model.user])
                if self.model.subject:
                    cmd.extend(['--subject', self.model.subject])
                if self.model.procedures:
                    cmd.extend(['--procedures', *self.model.procedures])
                if self.model.projects:
                    cmd.extend(['--projects', *self.model.projects])
                for key in self.task_arguments:
                    if isinstance(self.task_arguments[key], Iterable) and not isinstance(self.task_arguments[key], str):
                        cmd.extend([str(key)])
                        for value in self.task_arguments[key]:
                            cmd.extend([value])
                    else:
                        cmd.extend([key, self.task_arguments[key]])
                cmd.extend(['--weight', f'{weight}'])
                cmd.extend(['--log-level', 'DEBUG' if self.debug else 'INFO'])
                cmd.append('--wizard')
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                if self.running_task_process is None:
                    self.uiPlainTextEditLog.clear()
                    self._set_plaintext_char_color(self.uiPlainTextEditLog, 'White')
                    self.uiPlainTextEditLog.appendPlainText(f'Starting subprocess: {self.model.task_name} ...\n')
                    log.info('Starting subprocess')
                    log.info(subprocess.list2cmdline(cmd))
                    self.running_task_process = QtCore.QProcess()
                    self.running_task_process.setWorkingDirectory(BASE_DIR)
                    self.running_task_process.setProcessChannelMode(QtCore.QProcess.SeparateChannels)
                    self.running_task_process.finished.connect(self._on_task_finished)
                    self.running_task_process.readyReadStandardOutput.connect(self._on_read_standard_output)
                    self.running_task_process.readyReadStandardError.connect(self._on_read_standard_error)
                    self.running_task_process.start(shutil.which('python'), cmd)
                self.uiPushStart.setStatusTip('stop the session after the current trial')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
                self.tabWidget.setCurrentIndex(self.tabWidget.indexOf(self.tabLog))
            case 'Stop':
                self.uiPushStart.setEnabled(False)
                if self.model.session_folder and self.model.session_folder.exists():
                    self.model.session_folder.joinpath('.stop').touch()

    @staticmethod
    def _set_plaintext_char_color(widget: QtWidgets.QPlainTextEdit, color: str = 'White') -> None:
        """
        Set the foreground color of characters in a QPlainTextEdit widget.

        Parameters
        ----------
        widget : QtWidgets.QPlainTextEdit
            The QPlainTextEdit widget whose character color is to be set.

        color : str, optional
            The name of the color to set. Default is 'White'. Should be a valid color name
            recognized by QtGui.QColorConstants. If the provided color name is not found,
            it defaults to QtGui.QColorConstants.White.
        """
        color = getattr(QtGui.QColorConstants, color, QtGui.QColorConstants.White)
        char_format = widget.currentCharFormat()
        char_format.setForeground(QtGui.QBrush(color))
        widget.setCurrentCharFormat(char_format)

    def _on_read_standard_output(self):
        """
        Read and process standard output entries.

        Reads standard output from a running task process, processes each entry,
        extracts color information, sets character color in the QPlainTextEdit widget,
        and appends time and message information to the widget.
        """
        data = self.running_task_process.readAllStandardOutput().data().decode('utf-8', 'ignore').strip()
        entries = re.finditer(REGEX_STDOUT, data)
        for entry in entries:
            color = ANSI_COLORS.get(entry.groupdict().get('color', '37'), 'White')
            self._set_plaintext_char_color(self.uiPlainTextEditLog, color)
            time = entry.groupdict().get('time', '')
            msg = entry.groupdict().get('message', '')
            self.uiPlainTextEditLog.appendPlainText(f'{time} {msg}')
        if self.debug:
            print(data)

    def _on_read_standard_error(self):
        """
        Read and process standard error entries.

        Reads standard error from a running task process, sets character color
        in the QPlainTextEdit widget to indicate an error (Red), and appends
        the error message to the widget.
        """
        data = self.running_task_process.readAllStandardError().data().decode('utf-8', 'ignore').strip()
        self._set_plaintext_char_color(self.uiPlainTextEditLog, 'Red')
        self.uiPlainTextEditLog.appendPlainText(data)
        if self.debug:
            print(data)

    def _on_task_finished(self, exit_code, exit_status):
        self._set_plaintext_char_color(self.uiPlainTextEditLog, 'White')
        self.uiPlainTextEditLog.appendPlainText('\nSubprocess finished.')
        if exit_code:
            msg_box = QtWidgets.QMessageBox(parent=self)
            msg_box.setWindowTitle('Oh no!')
            msg_box.setText('The task was terminated with an error.\nPlease check the log for details.')
            msg_box.setIcon(QtWidgets.QMessageBox().Critical)
            msg_box.exec_()

        self.running_task_process = None

        # re-enable UI elements
        self.uiPushStart.setText('Start')
        self.uiPushStart.setStatusTip('start the session')
        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._enable_ui_elements()

        # recall state of Bpod status LED
        bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])
        bpod.set_status_led(self.uiPushStatusLED.isChecked())

        if (task_settings_file := Path(self.model.raw_data_folder).joinpath('_iblrig_taskSettings.raw.json')).exists():
            with open(task_settings_file) as fid:
                session_data = json.load(fid)

            # check if session was a dud
            if (ntrials := session_data['NTRIALS']) < 42 and 'spontaneous' not in self.model.task_name:
                answer = QtWidgets.QMessageBox.question(
                    self,
                    'Is this a dud?',
                    f"The session consisted of only {ntrials:d} trial"
                    f"{'s' if ntrials > 1 else ''} and appears to be a dud.\n\n"
                    f"Should it be deleted?",
                )
                if answer == QtWidgets.QMessageBox.Yes:
                    shutil.rmtree(self.model.session_folder)
                    return

            # manage poop count
            dlg = QtWidgets.QInputDialog()
            droppings, ok = dlg.getInt(
                self,
                'Droppings',
                'Number of droppings:',
                value=0,
                min=0,
                flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint,
            )
            session_data['POOP_COUNT'] = droppings
            with open(task_settings_file, 'w') as fid:
                json.dump(session_data, fid, indent=4, sort_keys=True, default=str)

    def flush(self):
        # paint button blue when in toggled state
        self.uiPushFlush.setStyleSheet(
            'QPushButton {background-color: rgb(128, 128, 255);}' if self.uiPushFlush.isChecked() else ''
        )
        self._enable_ui_elements()

        try:
            bpod = Bpod(
                self.model.hardware_settings['device_bpod']['COM_BPOD'],
                skip_initialization=True,
                disable_behavior_ports=[1, 2, 3],
            )
            bpod.open_valve(self.uiPushFlush.isChecked())
        except (OSError, BpodErrorException):
            print(traceback.format_exc())
            print('Cannot find bpod - is it connected?')
            self.uiPushFlush.setChecked(False)
            self.uiPushFlush.setStyleSheet('')
            return

    def toggle_status_led(self, is_toggled: bool):
        # paint button green when in toggled state
        self.uiPushStatusLED.setStyleSheet('QPushButton {background-color: rgb(128, 255, 128);}' if is_toggled else '')
        self._enable_ui_elements()

        try:
            bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'], skip_initialization=True)
            bpod.set_status_led(is_toggled)
        except (OSError, BpodErrorException, AttributeError):
            self.uiPushStatusLED.setChecked(False)
            self.uiPushStatusLED.setStyleSheet('')

    def _enable_ui_elements(self):
        is_running = self.uiPushStart.text() == 'Stop'

        self.uiPushStart.setEnabled(
            not self.uiPushFlush.isChecked()
            and len(self.uiListProjects.selectedIndexes()) > 0
            and len(self.uiListProcedures.selectedIndexes()) > 0
        )
        self.uiPushPause.setEnabled(is_running)
        self.uiPushFlush.setEnabled(not is_running)
        self.uiPushReward.setEnabled(not is_running)
        self.uiPushStatusLED.setEnabled(not is_running)
        self.uiCheckAppend.setEnabled(not is_running)
        self.uiGroupParameters.setEnabled(not is_running)
        self.uiGroupTaskParameters.setEnabled(not is_running)
        self.uiGroupTools.setEnabled(not is_running)
        self.repaint()


class WorkerSignals(QtCore.QObject):
    """
    Signals used by the Worker class to communicate with the main thread.

    Attributes
    ----------
    finished : QtCore.pyqtSignal
        Signal emitted when the worker has finished its task.

    error : QtCore.pyqtSignal(tuple)
        Signal emitted when an error occurs. The signal carries a tuple with the exception type,
        exception value, and the formatted traceback.

    result : QtCore.pyqtSignal(Any)
        Signal emitted when the worker has successfully completed its task. The signal carries
        the result of the task.

    progress : QtCore.pyqtSignal(int)
        Signal emitted to report progress during the task. The signal carries an integer value.
    """

    finished: QtCore.pyqtSignal = QtCore.pyqtSignal()
    error: QtCore.pyqtSignal = QtCore.pyqtSignal(tuple)
    result: QtCore.pyqtSignal = QtCore.pyqtSignal(object)
    progress: QtCore.pyqtSignal = QtCore.pyqtSignal(int)


class Worker(QtCore.QRunnable):
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


class LoginWindow(QtWidgets.QDialog, Ui_login):
    def __init__(self, parent: RigWizard, username: str = '', password: str = '', remember: bool = False):
        super().__init__(parent)
        self.setupUi(self)
        self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.labelServer.setText(str(parent.model.iblrig_settings['ALYX_URL']))
        self.lineEditUsername.setText(username)
        self.lineEditPassword.setText(password)
        self.checkBoxRememberMe.setChecked(remember)
        self.lineEditUsername.textChanged.connect(self._onTextChanged)
        self.lineEditPassword.textChanged.connect(self._onTextChanged)
        self.toggle_password = self.lineEditPassword.addAction(
            QtGui.QIcon(':/images/hide'), QtWidgets.QLineEdit.ActionPosition.TrailingPosition
        )
        self.toggle_password.triggered.connect(self._toggle_password_visibility)
        self.toggle_password.setCheckable(True)
        if len(username) > 0:
            self.lineEditPassword.setFocus()
        self._onTextChanged()
        self.exec()

    def _onTextChanged(self):
        enable_ok = len(self.lineEditUsername.text()) > 0 and len(self.lineEditPassword.text()) > 0
        self.buttonBox.button(self.buttonBox.Ok).setEnabled(enable_ok)

    def _toggle_password_visibility(self):
        if self.toggle_password.isChecked():
            self.toggle_password.setIcon(QtGui.QIcon(':/images/show'))
            self.lineEditPassword.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)
        else:
            self.toggle_password.setIcon(QtGui.QIcon(':/images/hide'))
            self.lineEditPassword.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)


class UpdateNotice(QtWidgets.QDialog, Ui_update):
    """
    A dialog for displaying update notices.

    This class is used to create a dialog for displaying update notices.
    It shows information about the available update and provides a changelog.

    Parameters
    ----------
    parent : QtWidgets.QWidget
        The parent widget associated with this dialog.

    update_available : bool
        Indicates if an update is available.

    version : str
        The version of the available update.

    Attributes
    ----------
    None

    Methods
    -------
    None
    """

    def __init__(self, parent: QtWidgets.QWidget, version: str) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.uiLabelHeader.setText(f'Update to iblrig {version} is available.')
        self.uiTextBrowserChanges.setMarkdown(get_changelog())
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.exec()


class SubjectDetailsWorker(QThread):
    subject_name: str | None = None
    result: tuple[dict, dict] | None = None

    def __init__(self, subject_name):
        super().__init__()
        self.subject_name = subject_name

    def run(self):
        self.result = get_subject_training_info(self.subject_name)


class ValveCalibrationDialog(QtWidgets.QDialog, Ui_valve):
    scale: Scale | None = None
    scale_text_changed = QtCore.pyqtSignal(str)
    scale_stable_changed = QtCore.pyqtSignal(bool)
    _grams = float('nan')
    _stable = False
    _next_calibration_step = 1
    _scale_update_ms = 100

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        hw_settings: HardwareSettings = self.parent().model.hardware_settings
        self.bpod = Bpod(hw_settings.device_bpod.COM_BPOD, skip_initialization=True, disable_behavior_ports=[0, 1, 2, 3])

        self.font_database = QtGui.QFontDatabase
        self.font_database.addApplicationFont(':/fonts/7-Segment')
        self.lineEditGrams.setFont(QtGui.QFont('7-Segment', 30))
        self.action_grams = self.lineEditGrams.addAction(
            QtGui.QIcon(':/images/grams'), QtWidgets.QLineEdit.ActionPosition.TrailingPosition
        )
        self.action_stable = self.lineEditGrams.addAction(
            QtGui.QIcon(':/images/stable'), QtWidgets.QLineEdit.ActionPosition.LeadingPosition
        )
        self.action_grams.setVisible(False)
        self.action_stable.setVisible(False)
        self.scale_text_changed.connect(self.display_scale_text)
        self.scale_stable_changed.connect(self.display_scale_stable)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(QtCore.Qt.WindowModality.ApplicationModal)

        self.valve = Valve(hw_settings.device_valve)

        # set up scale reading
        self.scale_timer = QtCore.QTimer()
        if hw_settings.device_scale.COM_SCALE is not None:
            worker = Worker(self.initialize_scale, port=hw_settings.device_scale.COM_SCALE)
            worker.signals.result.connect(self._on_initialize_scale_result)
            QThreadPool.globalInstance().tryStart(worker)
        else:
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignCenter)
            self.lineEditGrams.setText('no Scale')

        # set up plot widget
        time_range = np.linspace(*self.valve.calibration_range, 100)
        self.curve = pg.PlotCurveItem(name='Current Calibration')
        self.curve.setData(x=list(time_range), y=self.valve.values.ms2ul(time_range), pen='gray')
        self.curve.setPen('gray', width=2, style=QtCore.Qt.DashLine)
        self.points = pg.ScatterPlotItem()
        self.points.setData(x=self.valve.values.open_times_ms, y=self.valve.values.volumes_ul)
        self.points.setPen('black')
        self.points.setBrush('black')

        self.uiPlot.hideButtons()
        self.uiPlot.setMenuEnabled(False)
        self.uiPlot.setMouseEnabled(x=False, y=False)
        self.uiPlot.setBackground(None)
        self.uiPlot.addLegend()
        self.uiPlot.addItem(self.curve)
        self.uiPlot.addItem(self.points)
        self.uiPlot.setLabel('bottom', 'Opening Time [ms]')
        self.uiPlot.setLabel('left', 'Volume [μL]')
        self.uiPlot.getViewBox().setLimits(xMin=0, yMin=0)

        self.buttonBox.button(self.buttonBox.Ok).setText('Save')
        self.buttonBox.button(self.buttonBox.Ok).setEnabled(False)
        self.pushButtonPulseValve.clicked.connect(self.pulse_valve)
        self.pushButtonToggleValve.clicked.connect(self.toggle_valve)
        self.pushButtonTareScale.clicked.connect(self.tare)

        self.machine = QtCore.QStateMachine()
        self.states: list[QtCore.QState] = []

        self._add_main_state(
            help_text=(
                'This is a step-by-step guide for calibrating the valve of your rig. You can abort the process at any time by '
                'pressing Cancel.'
            )
        )

        self._add_main_state(
            help_text=(
                'Place a small beaker on the scale and position the lick spout directly above it.\n\nMake sure that neither the '
                'lick spout itself nor the tubing touch the beaker or the scale and that the water drops can freely fall into '
                'the beaker.'
            )
        )

        self._add_main_state(
            help_text=(
                'Use the valve controls above to advance the flow of the water until there are no visible pockets of air within '
                'the tubing and first drops start falling into the beaker.'
            )
        )

        state = self._add_main_state(
            help_text=('Calibration is finished.\n\nClick Save to store the calibration or Cancel to discard it.'),
            final_state=True,
        )
        state.assignProperty(self.commandLinkNext, 'visible', False)
        state.assignProperty(self.buttonBox.button(self.buttonBox.Ok), 'enabled', True)

        self.machine.start()
        self.show()

    def _add_main_state(self, help_text: str | None = None, final_state: bool = False) -> QtCore.QState:
        idx = len(self.states)
        state = QtCore.QState()
        if help_text is not None:
            state.assignProperty(self.labelGuidedCalibration, 'text', help_text)
        self.machine.addState(state)
        if idx == 0:
            self.machine.setInitialState(state)
        elif idx > 0:
            self.states[-1].addTransition(self.commandLinkNext.clicked, state)
        if final_state:
            state.addTransition(state.finished, QtCore.QFinalState())
        self.states.append(state)
        return state

    def initialize_scale(self, port: str) -> bool:
        try:
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignCenter)
            self.lineEditGrams.setText('Starting')
            self.scale = Scale(port)
            return True
        except (AssertionError, SerialException):
            log.error(f'Error initializing OHAUS scale on {port}.')
            return False

    def _on_initialize_scale_result(self, success: bool):
        if success:
            self.lineEditGrams.setEnabled(True)
            self.pushButtonTareScale.setEnabled(True)
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignRight)
            self.lineEditGrams.setText('')
            self.scale_timer.timeout.connect(self.get_scale_reading)
            self.action_grams.setVisible(True)
            self.get_scale_reading()
            self.scale_timer.start(self._scale_update_ms)
        else:
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignCenter)
            self.lineEditGrams.setText('Error')

    def get_scale_reading(self):
        grams, stable = self.scale.get_grams()
        if grams != self._grams:
            self.scale_text_changed.emit(f'{grams:0.2f}')
        if stable != self._stable:
            self.scale_stable_changed.emit(stable)
        self._grams = grams
        self._stable = stable

    @QtCore.pyqtSlot(str)
    def display_scale_text(self, value: str):
        self.lineEditGrams.setText(value)

    @QtCore.pyqtSlot(bool)
    def display_scale_stable(self, value: bool):
        self.action_stable.setVisible(value)

    # def guided_calibration(self):
    #     guide_string = self._guide_strings.get(self._next_calibration_step, '')
    #     self.labelGuidedCalibration.setText(guide_string)
    #     match self._next_calibration_step:
    #         case 3:
    #             self.clear_drop()
    #         case 4:
    #             self.tare()
    #             worker = Worker(self.bpod.pulse_valve_repeatedly, repetitions=100, open_time_s=0.05, close_time_s=0.05)
    #             QThreadPool.globalInstance().tryStart(worker)
    #             # worker.signals.result.connect(self._on_initialize_scale_result)
    #             # self.bpod.pulse_valve_repeatedly(100, 0.05)
    #     self._next_calibration_step += 1

    def toggle_valve(self):
        state = self.pushButtonToggleValve.isChecked()
        self.pushButtonToggleValve.setStyleSheet('QPushButton {background-color: rgb(128, 128, 255);}' if state else '')
        try:
            self.bpod.open_valve(open=state)
        except (OSError, BpodErrorException):
            print(traceback.format_exc())
            print('Cannot find bpod - is it connected?')
            self.uiPushFlush.setChecked(False)
            self.uiPushFlush.setStyleSheet('')

    def pulse_valve(self):
        self.bpod.pulse_valve(0.05)

    def clear_drop(self):
        initial_grams = self.scale.get_stable_grams()
        timer = QtCore.QTimer()
        timer_callback = functools.partial(self.clear_crop_callback, initial_grams, timer)
        timer.timeout.connect(timer_callback)
        timer.start(500)

    def clear_crop_callback(self, initial_grams: float, timer: QtCore.QTimer):
        if self.scale.get_grams()[0] > initial_grams + 0.02:
            timer.stop()
            return
        self.pulse_valve()

    def tare(self):
        if self.scale is not None:
            self.scale_timer.stop()
            self.scale_text_changed.emit('------')
            self._grams = float('nan')
            worker = Worker(self.scale.tare)
            worker.signals.result.connect(self._on_tare_finished)
            QThreadPool.globalInstance().tryStart(worker)

    @QtCore.pyqtSlot(object)
    def _on_tare_finished(self, value: bool):
        QtCore.QTimer.singleShot(200, lambda: self.scale_timer.start(self._scale_update_ms))

    def closeEvent(self, event) -> bool:
        if self.scale is not None:
            self.scale_timer.stop()
        if self.machine.started:
            self.machine.stop()


class Frame2TTLCalibrationDialog(QtWidgets.QDialog, Ui_frame2ttl):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(QtCore.Qt.WindowModality.ApplicationModal)

        hw_settings = self.parent().model.hardware_settings
        self.frame2ttl = Frame2TTL(port=hw_settings.device_frame2ttl.COM_F2TTL)
        self.target = Frame2TTLCalibrationTarget(self, color=QtGui.QColorConstants.White)
        self.light = None
        self.dark = None
        self._success = True

        self.uiLabelPortValue.setText(self.frame2ttl.portstr)
        self.uiLabelHardwareValue.setText(str(self.frame2ttl.hw_version))
        self.uiLabelFirmwareValue.setText(str(self.frame2ttl.fw_version))
        self.buttonBox.buttons()[0].setEnabled(False)
        self.show()

        # start worker for first calibration step: light condition
        worker = Worker(self.frame2ttl.calibrate, condition='light')
        worker.signals.result.connect(self._on_calibrate_light_result)
        QThreadPool.globalInstance().tryStart(worker)
        self.uiLabelLightValue.setText('calibrating ...')

    def _on_calibrate_light_result(self, result: tuple[int, bool]):
        (self.light, self._success) = result
        self.uiLabelLightValue.setText(f'{self.light} {self.frame2ttl.unit_str}')

        # start worker for second calibration step: dark condition
        self.target.color = QtGui.QColorConstants.Black
        worker = Worker(self.frame2ttl.calibrate, condition='dark')
        worker.signals.result.connect(self._on_calibrate_dark_result)
        QThreadPool.globalInstance().tryStart(worker)
        self.uiLabelDarkValue.setText('calibrating ...')

    def _on_calibrate_dark_result(self, result: tuple[int, bool]):
        (self.dark, self._success) = result
        self.uiLabelDarkValue.setText(f'{self.dark} {self.frame2ttl.unit_str}')

        if self._success:
            self.frame2ttl.set_thresholds(light=self.light, dark=self.dark)
            self.parent().model.hardware_settings.device_frame2ttl.F2TTL_DARK_THRESH = self.dark
            self.parent().model.hardware_settings.device_frame2ttl.F2TTL_LIGHT_THRESH = self.light
            self.parent().model.hardware_settings.device_frame2ttl.F2TTL_CALIBRATION_DATE = datetime.date.today()
            save_pydantic_yaml(self.parent().model.hardware_settings)
            self.uiLabelResult.setText('Calibration successful.\nSettings have been updated.')
        else:
            self.uiLabelResult.setText('Calibration failed.\nVerify that sensor is placed correctly.')
        self.buttonBox.buttons()[0].setEnabled(True)
        self.frame2ttl.close()


class Frame2TTLCalibrationTarget(QtWidgets.QDialog):
    def __init__(
        self,
        parent,
        color: QtGui.QColor = QtGui.QColorConstants.White,
        screen_index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        rel_pos_x: float = 1.33,
        rel_pos_y: float = -1.03,
        rel_extent_x: float = 0.2,
        rel_extent_y: float = 0.2,
        **kwargs,
    ):
        # try to detect screen_index, get screen dimensions
        if screen_index is None:
            for screen_index, screen in enumerate(QtWidgets.QApplication.screens()):
                if screen.size().width() == 2048 and screen.size().height() == 1536:
                    break
            else:
                log.warning('Defaulting to screen index 0.')
                screen_index = 0
                screen = QtWidgets.QApplication.screens()[0]

        # convert relative parameters (used in bonsai scripts) to width and height
        if width is None and height is None:
            screen_width = screen.geometry().width()
            screen_height = screen.geometry().height()
            width = round(screen_width - (screen_width + (rel_pos_x - rel_extent_x / 2) * screen_height) / 2)
            height = round(screen_height - (1 - rel_pos_y - rel_extent_y / 2) * screen_height / 2)

        # display frameless QDialog with given color
        super().__init__(parent, **kwargs)
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Dialog)
        self.setAutoFillBackground(True)
        self._set_color(color)
        self.setFixedSize(width, height)
        screen_geometry = QtWidgets.QApplication.desktop().screenGeometry(screen_index)
        self.move(
            QtCore.QPoint(
                screen_geometry.x() + screen_geometry.width() - width, screen_geometry.y() + screen_geometry.height() - height
            )
        )
        self.show()
        QtTest.QTest.qWait(500)

    def _set_color(self, color: QtGui.QColor):
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)

    @property
    def color(self) -> QtGui.QColor:
        return self.palette().color(QtGui.QPalette.Window)

    @color.setter
    def color(self, color: QtGui.QColor):
        self._set_color(color)
        self.update()
        QtTest.QTest.qWait(500)


class CustomWebEnginePage(QWebEnginePage):
    """
    Custom implementation of QWebEnginePage to handle navigation requests.

    This class overrides the acceptNavigationRequest method to handle link clicks.
    If the navigation type is a link click and the clicked URL does not start with
    a specific prefix (URL_DOC), it opens the URL in the default web browser.
    Otherwise, it delegates the handling to the base class.

    Adapted from: https://www.pythonguis.com/faq/qwebengineview-open-links-new-window/
    """

    def acceptNavigationRequest(self, url: QtCore.QUrl, navigation_type: QWebEnginePage.NavigationType, is_main_frame: bool):
        """
        Decide whether to allow or block a navigation request.

        Parameters
        ----------
        url : QUrl
            The URL being navigated to.

        navigation_type : QWebEnginePage.NavigationType
            The type of navigation request.

        is_main_frame : bool
            Indicates whether the request is for the main frame.

        Returns
        -------
        bool
            True if the navigation request is accepted, False otherwise.
        """
        if navigation_type == QWebEnginePage.NavigationTypeLinkClicked and not url.url().startswith(URL_DOC):
            webbrowser.open(url.url())
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', dest='debug', help='increase logging verbosity')
    args = parser.parse_args()

    if args.debug:
        setup_logger(name=None, level='DEBUG')
    else:
        setup_logger(name='iblrig', level='INFO')
    QtCore.QCoreApplication.setOrganizationName('International Brain Laboratory')
    QtCore.QCoreApplication.setOrganizationDomain('internationalbrainlab.org')
    QtCore.QCoreApplication.setApplicationName('IBLRIG Wizard')

    if os.name == 'nt':
        app_id = f'IBL.iblrig.wizard.{iblrig.__version__}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    app = QtWidgets.QApplication(['', '--no-sandbox'])
    app.setStyle('Fusion')
    w = RigWizard(debug=args.debug)
    w.show()
    app.exec()


if __name__ == '__main__':
    main()
