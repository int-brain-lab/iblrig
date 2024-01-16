import argparse
import ctypes
import importlib
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
import webbrowser
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, QThreadPool
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWidgets import QStyle
from requests import HTTPError

import iblrig.hardware_validation
import iblrig.path_helper
import iblrig_tasks
from iblrig.base_tasks import EmptySession
from iblrig.choiceworld import get_subject_training_info, training_phase_from_contrast_set
from iblrig.constants import BASE_DIR
from iblrig.gui.ui_login import Ui_login
from iblrig.gui.ui_update import Ui_update
from iblrig.gui.ui_wizard import Ui_wizard
from iblrig.hardware import Bpod
from iblrig.misc import _get_task_argument_parser
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings
from iblrig.tools import alyx_reachable, get_anydesk_id, internet_available
from iblrig.version_management import check_for_updates, get_changelog, is_dirty
from iblutil.util import setup_logger
from one.api import ONE
from one.webclient import AlyxClient
from pybpodapi import exceptions

try:
    import iblrig_custom_tasks

    CUSTOM_TASKS = True
except ImportError:
    CUSTOM_TASKS = False
    pass

log = logging.getLogger(__name__)

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
    one: Optional[ONE] = None
    procedures: list | None = None
    projects: list | None = None
    task_name: str | None = None
    user: str | None = None
    subject: str | None = None
    session_folder: Path | None = None
    test_subject_name = 'test_subject'
    subject_details_worker = None
    subject_details: tuple | None = None

    def __post_init__(self):
        self.iblrig_settings: RigSettings = load_pydantic_yaml(RigSettings)
        self.hardware_settings: HardwareSettings = load_pydantic_yaml(HardwareSettings)

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
        self, username: str, password: str | None = None, do_cache: bool = False, alyx_client: AlyxClient | None = None
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

        # # since we are connecting to Alyx, validate some parameters to ensure a smooth extraction
        # result = iblrig.hardware_validation.ValidateAlyxLabLocation().run(self.one)
        # if result.status == 'FAIL' and gui:
        #     QtWidgets.QMessageBox().critical(None, 'Error', f'{result.message}\n\n{result.solution}')

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

    def get_subject_details(self, subject):
        self.subject_details_worker = SubjectDetailsWorker(subject)
        self.subject_details_worker.finished.connect(self.process_subject_details)
        self.subject_details_worker.start()

    def process_subject_details(self):
        self.subject_details = SubjectDetailsWorker.result


class RigWizard(QtWidgets.QMainWindow, Ui_wizard):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.settings = QtCore.QSettings()
        self.move(self.settings.value('pos', self.pos(), QtCore.QPoint))

        self.model = RigWizardModel()
        self.model2view()

        # default to biasedChoiceWorld
        if (idx := self.uiComboTask.findText('_iblrig_tasks_biasedChoiceWorld')) >= 0:
            self.uiComboTask.setCurrentIndex(idx)

        # connect widgets signals to slots
        self.uiActionTrainingLevelV7.triggered.connect(self._on_menu_training_level_v7)
        self.uiComboTask.currentTextChanged.connect(self.controls_for_extra_parameters)
        self.uiComboSubject.currentTextChanged.connect(self.model.get_subject_details)
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushStart.clicked.connect(self.start_stop)
        self.uiPushPause.clicked.connect(self.pause)
        self.uiListProjects.clicked.connect(self._enable_ui_elements)
        self.uiListProcedures.clicked.connect(self._enable_ui_elements)
        self.lineEditSubject.textChanged.connect(self._filter_subjects)

        self.uiPushStatusLED.setChecked(self.settings.value('bpod_status_led', True, bool))
        self.uiPushStatusLED.toggled.connect(self.toggle_status_led)
        self.toggle_status_led(self.uiPushStatusLED.isChecked())

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

        # documentation
        self.uiPushWebHome.clicked.connect(lambda: self.webEngineView.load(QtCore.QUrl(URL_DOC)))
        self.uiPushWebBrowser.clicked.connect(lambda: webbrowser.open(str(self.webEngineView.url().url())))
        self.webEngineView.setPage(CustomWebEnginePage(self))
        self.webEngineView.setUrl(QtCore.QUrl(URL_DOC))
        self.webEngineView.urlChanged.connect(self._on_doc_url_changed)

        # tab: about
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
            logged_in = self.model.login(username)
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
                    logged_in = self.model.login(username=username, password=password, do_cache=remember)
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
            QtCore.QMetaProperty
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
                cmd.append('--wizard')
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                if self.running_task_process is None:
                    log.info('Starting subprocess')
                    log.info(subprocess.list2cmdline(cmd))
                    self.running_task_process = QtCore.QProcess()
                    self.running_task_process.setWorkingDirectory(BASE_DIR)
                    self.running_task_process.setProcessChannelMode(QtCore.QProcess.ForwardedChannels)
                    self.running_task_process.finished.connect(self._on_task_finished)
                    self.running_task_process.start(shutil.which('python'), cmd)
                self.uiPushStart.setStatusTip('stop the session after the current trial')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
            case 'Stop':
                self.uiPushStart.setEnabled(False)
                if self.model.session_folder and self.model.session_folder.exists():
                    self.model.session_folder.joinpath('.stop').touch()

    def _on_task_finished(self, exit_code, exit_status):
        if exit_code:
            msg_box = QtWidgets.QMessageBox(parent=self)
            msg_box.setWindowTitle('Oh no!')
            msg_box.setText('The task was terminated with an error.\nPlease check the command-line output for details.')
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
            bpod.manual_override(bpod.ChannelTypes.OUTPUT, bpod.ChannelNames.VALVE, 1, self.uiPushFlush.isChecked())
        except (OSError, exceptions.bpod_error.BpodErrorException):
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
        except (OSError, exceptions.bpod_error.BpodErrorException, AttributeError):
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

        Returns
        -------
        None
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
    setup_logger('iblrig', level='INFO')
    QtCore.QCoreApplication.setOrganizationName('International Brain Laboratory')
    QtCore.QCoreApplication.setOrganizationDomain('internationalbrainlab.org')
    QtCore.QCoreApplication.setApplicationName('IBLRIG Wizard')

    if os.name == 'nt':
        app_id = f'IBL.iblrig.wizard.{iblrig.__version__}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    app = QtWidgets.QApplication(['', '--no-sandbox'])
    app.setStyle('Fusion')
    w = RigWizard()
    w.show()
    app.exec()


if __name__ == '__main__':
    main()
