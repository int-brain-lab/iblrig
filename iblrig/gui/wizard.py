import argparse
import ctypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import traceback
from collections import OrderedDict
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pyqtgraph as pg
from pydantic import ValidationError
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QStyle
from requests import HTTPError
from serial import SerialException
from typing_extensions import override

import iblrig.hardware_validation
import iblrig.path_helper
import iblrig_tasks
from ibllib.io.raw_data_loaders import load_settings
from iblrig.base_tasks import EmptySession
from iblrig.choiceworld import compute_adaptive_reward_volume, get_subject_training_info, training_phase_from_contrast_set
from iblrig.constants import BASE_DIR
from iblrig.gui.frame2ttl import Frame2TTLCalibrationDialog
from iblrig.gui.splash import Splash
from iblrig.gui.tab_about import TabAbout
from iblrig.gui.tab_data import TabData
from iblrig.gui.tab_docs import TabDocs
from iblrig.gui.tab_log import TabLog
from iblrig.gui.tools import DiskSpaceIndicator, Worker
from iblrig.gui.ui_login import Ui_login
from iblrig.gui.ui_update import Ui_update
from iblrig.gui.ui_wizard import Ui_wizard
from iblrig.gui.validation import SystemValidationDialog
from iblrig.gui.valve import ValveCalibrationDialog
from iblrig.hardware import Bpod
from iblrig.hardware_validation import Status
from iblrig.misc import _get_task_argument_parser
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings
from iblrig.raw_data_loaders import load_task_jsonable
from iblrig.tools import alyx_reachable, internet_available
from iblrig.valve import Valve
from iblrig.version_management import check_for_updates, get_changelog
from iblutil.util import setup_logger
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

ANSI_COLORS: dict[str, str] = {'31': 'Red', '32': 'Green', '33': 'Yellow', '35': 'Magenta', '36': 'Cyan', '37': 'White'}
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
    free_reward_time: float | None = None
    file_iblrig_settings: Path | str | None = None
    file_hardware_settings: Path | str | None = None

    def __post_init__(self):
        self.iblrig_settings: RigSettings = load_pydantic_yaml(RigSettings, filename=self.file_iblrig_settings, do_raise=True)
        self.hardware_settings: HardwareSettings = load_pydantic_yaml(
            HardwareSettings, filename=self.file_hardware_settings, do_raise=True
        )

        self.free_reward_time = Valve(self.hardware_settings.device_valve).free_reward_time_sec

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
        spec = spec_from_file_location('task', self.all_tasks[task_name])
        task = module_from_spec(spec)
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

        # validate connection and some parameters now that we're connected
        try:
            self.alyx.rest('locations', 'read', id=self.hardware_settings.RIG_NAME)
        except HTTPError as ex:
            if ex.response.status_code not in (404, 400):  # file not found; auth error
                # Likely Alyx is down or server-side issue
                message = 'Failed to determine lab location on Alyx'
                solution = 'Check if Alyx is reachable'
            else:
                message = f'Could not find rig name {self.hardware_settings.RIG_NAME} in Alyx'
                solution = (
                    f'Please check the RIG_NAME key in hardware_settings.yaml and make sure it is created in Alyx here: '
                    f'{self.iblrig_settings.ALYX_URL}/admin/misc/lablocation/'
                )
            QtWidgets.QMessageBox().critical(None, 'Error', f'{message}\n\n{solution}')

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
                self.hardware_settings['device_bpod']['COM_BPOD'], skip_initialization=True, disable_behavior_ports=[1, 2, 3]
            )
            bpod.pulse_valve(open_time_s=self.free_reward_time)
        except (OSError, BpodErrorException):
            log.error('Cannot find bpod - is it connected?')
            return


class RigWizard(QtWidgets.QMainWindow, Ui_wizard):
    subject_details: tuple[dict, dict] | None = None
    new_subject_details = QtCore.pyqtSignal(dict, object)

    def __init__(self, **kwargs):
        super().__init__()
        self.setupUi(self)

        # load tabs
        self.tabLog = TabLog(parent=self.tabWidget)
        self.tabData = TabData(parent=self.tabWidget)
        self.tabDocs = TabDocs(parent=self.tabWidget)
        self.tabAbout = TabAbout(parent=self.tabWidget)
        self.tabWidget.addTab(self.tabLog, QtGui.QIcon(':/images/log'), 'Log')
        self.tabWidget.addTab(self.tabData, QtGui.QIcon(':/images/sessions'), 'Data')
        self.tabWidget.addTab(self.tabDocs, QtGui.QIcon(':/images/help'), 'Docs')
        self.tabWidget.addTab(self.tabAbout, QtGui.QIcon(':/images/about'), 'About')
        self.tabWidget.setCurrentIndex(0)

        self.debug = kwargs.get('debug', False)
        self.settings = QtCore.QSettings()

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
            description = ''
            for error in e.errors():
                key = '.'.join(error.get('loc', ''))
                val = error.get('input', '')
                msg = error.get('msg', '')
                description += (
                    f'<table>'
                    f'<tr><td><b>key:</b></td><td><td>{key}</td></tr>\n'
                    f'<tr><td><b>value:</b></td><td><td>{val}</td></tr>\n'
                    f'<tr><td><b>error:</b></td><td><td>{msg}</td></tr></table><br>\n'
                )
            self._show_error_dialog(title=f'Error validating {yml}', description=description.strip())
            raise e
        self.model2view()

        # default to biasedChoiceWorld
        if (idx := self.uiComboTask.findText('_iblrig_tasks_biasedChoiceWorld')) >= 0:
            self.uiComboTask.setCurrentIndex(idx)

        # connect widgets signals to slots
        self.uiActionValidateHardware.triggered.connect(self._on_validate_hardware)
        self.uiActionCalibrateFrame2ttl.triggered.connect(self._on_calibrate_frame2ttl)
        self.uiActionCalibrateValve.triggered.connect(self._on_calibrate_valve)
        self.uiActionTrainingLevelV7.triggered.connect(self._on_menu_training_level_v7)
        self.uiComboTask.currentTextChanged.connect(self.controls_for_extra_parameters)

        self.uiComboSubject.currentTextChanged.connect(self._get_subject_details)
        self.uiPushStart.clicked.connect(self.start_stop)
        self.uiPushPause.clicked.connect(self.pause)
        self.uiListProjects.clicked.connect(self._enable_ui_elements)
        self.uiListProcedures.clicked.connect(self._enable_ui_elements)
        self.lineEditSubject.textChanged.connect(self._filter_subjects)

        self._get_subject_details(self.uiComboSubject.currentText())
        self.new_subject_details.connect(self._set_automatic_values)
        self.uiComboTask.currentTextChanged.connect(lambda: self._set_automatic_values(*self.subject_details))

        self.running_task_process = None
        self.task_arguments = dict()
        self.task_settings_widgets = None

        self.uiPushStart.installEventFilter(self)
        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.uiPushPause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

        self.controller2model()

        self.tabWidget.currentChanged.connect(self._on_switch_tab)

        # username
        if self.iblrig_settings.ALYX_URL is not None:
            self.uiLineEditUser.returnPressed.connect(lambda w=self.uiLineEditUser: self._log_in_or_out(username=w.text()))
            self.uiPushButtonLogIn.released.connect(lambda w=self.uiLineEditUser: self._log_in_or_out(username=w.text()))
        else:
            self.uiLineEditUser.setPlaceholderText('')
            self.uiPushButtonLogIn.setEnabled(False)

        # tools
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushReward.clicked.connect(self.model.free_reward)
        self.uiPushReward.setStatusTip(
            f'Click to grant a free reward ({self.hardware_settings.device_valve.FREE_REWARD_VOLUME_UL:.1f} μL)'
        )
        self.uiPushStatusLED.setChecked(self.settings.value('bpod_status_led', True, bool))
        self.uiPushStatusLED.toggled.connect(self.toggle_status_led)
        self.toggle_status_led(self.uiPushStatusLED.isChecked())

        # statusbar / disk stats
        local_data = self.iblrig_settings['iblrig_local_data_path']
        local_data = Path(local_data) if local_data else Path.home().joinpath('iblrig_data')
        self.uiDiskSpaceIndicator = DiskSpaceIndicator(parent=self.statusbar, directory=local_data)
        self.uiDiskSpaceIndicator.setMaximumWidth(70)
        self.statusbar.addPermanentWidget(self.uiDiskSpaceIndicator)
        self.statusbar.setContentsMargins(0, 0, 6, 0)
        self.controls_for_extra_parameters()

        # disable control of LED if Bpod does not have the respective capability
        try:
            bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'], skip_initialization=True)
            self.uiPushStatusLED.setEnabled(bpod.can_control_led)
        except SerialException:
            pass

        # show splash-screen / store validation results
        splash_screen = Splash(parent=self)
        splash_screen.exec()
        self.validation_results = splash_screen.validation_results

        # check for update
        update_worker = Worker(check_for_updates)
        update_worker.signals.result.connect(self._on_check_update_result)
        QThreadPool.globalInstance().start(update_worker)

        # show GUI
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowFullscreenButtonHint)
        self.move(self.settings.value('pos', self.pos(), QtCore.QPoint))
        self.resize(self.settings.value('size', self.size(), QtCore.QSize))
        self.show()

        # show validation errors / warnings:
        if any(results := [r for r in self.validation_results if r.status in (Status.FAIL, Status.WARN)]):
            msg_box = QtWidgets.QMessageBox(parent=self)
            msg_box.setWindowTitle('IBLRIG System Validation')
            msg_box.setIcon(QtWidgets.QMessageBox().Warning)
            msg_box.setTextFormat(QtCore.Qt.TextFormat.RichText)
            text = f"The following issue{'s were' if len(results) > 1 else ' was'} detected:"
            for result in results:
                text = (
                    text + f"<br><br>\n"
                    f"<b>{'Warning' if result.status == Status.WARN else 'Failure'}:</b> {result.message}<br>\n"
                    f"{('<b>Suggestion:</b> ' + result.solution) if result.solution is not None else ''}"
                )
            text = text + '<br><br>\nPlease refer to the System Validation tool for more details.'
            msg_box.setText(text)
            msg_box.exec()

    @property
    def iblrig_settings(self) -> RigSettings:
        return self.model.iblrig_settings

    @property
    def hardware_settings(self) -> HardwareSettings:
        return self.model.hardware_settings

    def _get_subject_details(self, subject):
        worker = Worker(lambda: get_subject_training_info(subject))
        worker.signals.result.connect(self._on_subject_details_result)
        QThreadPool.globalInstance().start(worker)

    def _on_subject_details_result(self, result):
        self.subject_details = result
        self.new_subject_details.emit(*result)

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

    def _on_validate_hardware(self) -> None:
        SystemValidationDialog(self, hardware_settings=self.hardware_settings, rig_settings=self.iblrig_settings)

    def _on_calibrate_frame2ttl(self) -> None:
        Frame2TTLCalibrationDialog(self, hardware_settings=self.hardware_settings)

    def _on_calibrate_valve(self) -> None:
        ValveCalibrationDialog(self)

    def _on_menu_training_level_v7(self) -> None:
        """
        Prompt user for a session path to get v7 training level.

        This code will be removed and is here only for convenience while users transition from v7 to v8
        """

        # get session path
        if not (local_path := Path(r'C:\iblrig_data\Subjects')).exists():
            local_path = self.iblrig_settings.iblrig_local_data_path
        session_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Session Path', str(local_path), QtWidgets.QFileDialog.ShowDirsOnly
        )
        if session_path is None or session_path == '':
            return

        # get trials table
        file_jsonable = next(Path(session_path).glob('raw_behavior_data/_iblrig_taskData.raw.jsonable'), None)
        if file_jsonable is None:
            QtWidgets.QMessageBox().critical(self, 'Error', f'No jsonable found in {session_path}')
            return
        trials_table, _ = load_task_jsonable(file_jsonable)
        if trials_table.empty:
            QtWidgets.QMessageBox().critical(self, 'Error', f'No trials found in {session_path}')
            return

        # get task settings
        task_settings = load_settings(session_path, task_collection='raw_behavior_data')
        if task_settings is None:
            QtWidgets.QMessageBox().critical(self, 'Error', f'No task settings found in {session_path}')
            return

        # compute values
        contrast_set = trials_table['signed_contrast'].abs().unique()
        training_phase = training_phase_from_contrast_set(contrast_set)
        previous_reward_volume = (
            task_settings.get('ADAPTIVE_REWARD_AMOUNT_UL')
            or task_settings.get('REWARD_AMOUNT_UL')
            or task_settings.get('REWARD_AMOUNT')
        )
        reward_amount = compute_adaptive_reward_volume(
            subject_weight_g=task_settings['SUBJECT_WEIGHT'],
            reward_volume_ul=previous_reward_volume,
            delivered_volume_ul=trials_table['reward_amount'].sum(),
            ntrials=trials_table.shape[0],
        )
        stim_gain = trials_table['stim_gain'].values[-1]

        # display results
        box = QtWidgets.QMessageBox(parent=self)
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setModal(False)
        box.setWindowTitle('Training Level')
        box.setText(
            f'{session_path}\n\n'
            f'training phase:\t{training_phase}\n'
            f'reward:\t{reward_amount:.2f} uL\n'
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
                    description=f'Cannot connect to {self.iblrig_settings.ALYX_URL}',
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

    @override
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

    @override
    def closeEvent(self, event) -> None:
        def accept() -> None:
            self.settings.setValue('pos', self.pos())
            self.settings.setValue('size', self.size())
            self.settings.setValue('bpod_status_led', self.uiPushStatusLED.isChecked())
            self.toggle_status_led(is_toggled=True)
            bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'])  # bpod is a singleton
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
        args = sorted(self.model.get_task_extra_parser(self.model.task_name)._actions, key=lambda x: x.dest) + args
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
                        '--remote',
                    ]
                )
            )
        ]

        group = self.uiGroupTaskParameters
        layout = group.layout()
        self.task_settings_widgets = [None] * len(args)

        while layout.rowCount():
            layout.removeRow(0)

        for arg in args:
            param = str(max(arg.option_strings, key=len))
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
                # string options (-> combo-box)
                if isinstance(arg.choices, list):
                    widget = QtWidgets.QComboBox()
                    widget.addItems(arg.choices)
                    if arg.default:
                        widget.setCurrentIndex([widget.itemText(x) for x in range(widget.count())].index(arg.default))
                    widget.currentTextChanged.connect(lambda val, p=param: self._set_task_arg(p, val))
                    widget.currentTextChanged.emit(widget.currentText())

                # list of strings (-> line-edit)
                elif arg.nargs == '+':
                    widget = QtWidgets.QLineEdit()
                    if arg.default:
                        widget.setText(', '.join(arg.default))
                    widget.editingFinished.connect(
                        lambda p=param, w=widget: self._set_task_arg(p, [x.strip() for x in w.text().split(',')])
                    )
                    widget.editingFinished.emit()

                # single string (-> line-edit)
                else:
                    widget = QtWidgets.QLineEdit()
                    if arg.default:
                        widget.setText(arg.default)
                    widget.editingFinished.connect(lambda p=param, w=widget: self._set_task_arg(p, w.text()))
                    widget.editingFinished.emit()

            # create widget for list of floats
            elif arg.type is float and arg.nargs == '+':
                widget = QtWidgets.QLineEdit()
                if arg.default:
                    widget.setText(str(arg.default)[1:-1])
                widget.editingFinished.connect(
                    lambda p=param, w=widget: self._set_task_arg(p, [x.strip() for x in w.text().split(',')])
                )
                widget.editingFinished.emit()

            # create widget for adaptive gain
            if arg.dest == 'adaptive_gain':
                widget = QtWidgets.QDoubleSpinBox()
                widget.setDecimals(1)

            # create widget for numerical arguments
            elif arg.type in [float, int]:
                if arg.type is float:
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
                case 'probability_left' | 'probability_opto_stim':
                    widget.setMinimum(0.0)
                    widget.setMaximum(1.0)
                    widget.setSingleStep(0.1)
                    widget.setDecimals(2)

                case 'contrast_set_probability_type':
                    label = 'Probability Type'

                case 'session_template_id':
                    label = 'Session Template ID'
                    widget.setMinimum(0)
                    widget.setMaximum(11)

                case 'delay_secs':
                    label = 'Initial Delay, s'
                    widget.setMaximum(86400)

                case 'training_phase':
                    widget.setSpecialValueText('automatic')
                    widget.setMaximum(5)
                    widget.setMinimum(-1)
                    widget.setValue(-1)
                    widget.setObjectName('training_phase')

                case 'adaptive_reward':
                    label = 'Reward Amount, μl'
                    minimum = 1.4
                    widget.setSpecialValueText('automatic')
                    widget.setMaximum(3)
                    widget.setSingleStep(0.1)
                    widget.setMinimum(minimum)
                    widget.setValue(widget.minimum())
                    widget.valueChanged.connect(
                        lambda val, a=arg, m=minimum: self._set_task_arg(a.option_strings[0], str(val if val > m else -1))
                    )
                    widget.valueChanged.emit(widget.value())
                    widget.setObjectName('adaptive_reward')

                case 'reward_set_ul':
                    label = 'Reward Set, μl'

                case 'adaptive_gain':
                    label = 'Stimulus Gain'
                    minimum = 0
                    widget.setSpecialValueText('automatic')
                    widget.setSingleStep(0.1)
                    widget.setMinimum(minimum)
                    widget.setValue(widget.minimum())
                    widget.valueChanged.connect(
                        lambda val, a=arg, m=minimum: self._set_task_arg(a.option_strings[0], str(val) if val > m else 'None')
                    )
                    widget.valueChanged.emit(widget.value())
                    widget.setObjectName('adaptive_gain')

                case 'reward_amount_ul':
                    label = 'Reward Amount, μl'
                    widget.setSingleStep(0.1)
                    widget.setMinimum(0)

                case 'stim_gain':
                    label = 'Stimulus Gain'

                case 'stim_reverse':
                    label = 'Reverse Stimulus'

                case 'duration_spontaneous':
                    label = 'Spontaneous Activity, s'
                    widget.setMinimum(0)
                    widget.setMaximum(60 * 60 * 24 - 1)
                    widget.setValue(arg.default)

            widget.wheelEvent = lambda event: None
            layout.addRow(self.tr(label), widget)

        # add label to indicate absence of task specific parameters
        if layout.rowCount() == 0:
            layout.addRow(self.tr('(none)'), None)
            layout.itemAt(0, 0).widget().setEnabled(False)

    def _set_automatic_values(self, training_info: dict, session_info: dict | None):
        def _helper(name: str, format: str):
            value = training_info.get(name)
            if (widget := self.uiGroupTaskParameters.findChild(QtWidgets.QWidget, name)) is not None:
                if value is None:
                    default = ' (default)' if session_info is None else ''
                    widget.setSpecialValueText(f'automatic{default}')
                else:
                    default = ', default' if session_info is None else ''
                    widget.setSpecialValueText(f'automatic ({value:{format}}{default})')

        _helper('training_phase', 'd')
        _helper('adaptive_reward', '0.1f')
        _helper('adaptive_gain', '0.1f')

    def _set_task_arg(self, key, value):
        self.task_arguments[key] = value

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
                    decimals=2,
                    flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint,
                )
                if not ok or weight == 0:
                    self.uiPushStart.setText('Start')
                    self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                    self._enable_ui_elements()
                    return

                self.controller2model()

                logging.disable(logging.INFO)
                task = EmptySession(subject=self.model.subject, append=self.uiCheckAppend.isChecked(), interactive=False)
                logging.disable(logging.NOTSET)
                self.model.session_folder = task.paths['SESSION_FOLDER']
                if self.model.session_folder.joinpath('.stop').exists():
                    self.model.session_folder.joinpath('.stop').unlink()
                self.model.raw_data_folder = task.paths['SESSION_RAW_DATA_FOLDER']

                # disable Bpod status LED
                bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'])
                bpod.set_status_led(False)

                # close Bpod singleton so subprocess can access use the port
                bpod.close()

                # build the argument list for the subprocess
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
                for key, value in self.task_arguments.items():
                    if isinstance(value, list):
                        cmd.extend([key] + value)
                    elif isinstance(value, bool):
                        if value is True:
                            cmd.append(key)
                        else:
                            pass
                    else:
                        cmd.extend([key, value])
                cmd.extend(['--weight', f'{weight}'])
                cmd.extend(['--log-level', 'DEBUG' if self.debug else 'INFO'])
                cmd.append('--wizard')
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                if self.running_task_process is None:
                    self.tabLog.clear()
                    self.tabLog.appendText(f'Starting subprocess: {self.model.task_name} ...\n', 'White')
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
            time = entry.groupdict().get('time', '')
            msg = entry.groupdict().get('message', '')
            self.tabLog.appendText(f'{time} {msg}', color)
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
        self.tabLog.appendText(data, 'Red')
        if self.debug:
            print(data)

    def _on_task_finished(self, exit_code, exit_status):
        self.tabLog.appendText('\nSubprocess finished.', 'White')
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
        bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'])
        bpod.set_status_led(self.uiPushStatusLED.isChecked())

        if (task_settings_file := Path(self.model.raw_data_folder).joinpath('_iblrig_taskSettings.raw.json')).exists():
            with open(task_settings_file) as fid:
                session_data = json.load(fid)

            # check if session was a dud
            if (
                (ntrials := session_data['NTRIALS']) < 42
                and not any([x in self.model.task_name for x in ('spontaneous', 'passive')])
                and not self.uiCheckAppend.isChecked()
            ):
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
                self.hardware_settings['device_bpod']['COM_BPOD'],
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
            bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'], skip_initialization=True)
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


class LoginWindow(QtWidgets.QDialog, Ui_login):
    def __init__(self, parent: RigWizard, username: str = '', password: str = '', remember: bool = False):
        super().__init__(parent)
        self.setupUi(self)
        self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.labelServer.setText(str(parent.iblrig_settings['ALYX_URL']))
        self.lineEditUsername.setText(username)
        self.lineEditPassword.setText(password)
        self.checkBoxRememberMe.setChecked(remember)
        self.lineEditUsername.textChanged.connect(self._on_text_changed)
        self.lineEditPassword.textChanged.connect(self._on_text_changed)
        self.toggle_password = self.lineEditPassword.addAction(
            QtGui.QIcon(':/images/hide'), QtWidgets.QLineEdit.ActionPosition.TrailingPosition
        )
        self.toggle_password.triggered.connect(self._toggle_password_visibility)
        self.toggle_password.setCheckable(True)
        if len(username) > 0:
            self.lineEditPassword.setFocus()
        self._on_text_changed()
        self.exec()

    def _on_text_changed(self):
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
    """

    def __init__(self, parent: QtWidgets.QWidget, version: str) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.uiLabelHeader.setText(f'Update to iblrig {version} is available.')
        self.uiTextBrowserChanges.setMarkdown(get_changelog())
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.exec()


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
