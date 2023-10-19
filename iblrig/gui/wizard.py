from collections import OrderedDict
from dataclasses import dataclass
import importlib
import json
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable, Union, Optional, Iterable

import yaml
import traceback
import webbrowser
import ctypes
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, QThreadPool
from PyQt5.QtWidgets import QStyle

from one.api import ONE
import iblrig_tasks
try:
    import iblrig_custom_tasks
    CUSTOM_TASKS = True
except ImportError:
    CUSTOM_TASKS = False
    pass
import iblrig.path_helper
from iblrig.constants import BASE_DIR
from iblrig.misc import _get_task_argument_parser
from iblrig.base_tasks import BaseSession
from iblrig.hardware import Bpod
from iblrig.version_management import check_for_updates, get_changelog, is_dirty
from iblrig.gui.ui_wizard import Ui_wizard
from iblrig.gui.ui_update import Ui_update
from iblrig.choiceworld import get_subject_training_info
from iblutil.util import setup_logger
from pybpodapi import exceptions

log = setup_logger("iblrig")

PROCEDURES = [
    'Behavior training/tasks',
    'Ephys recording with acute probe(s)',
    'Ephys recording with chronic probe(s)',
    'Fiber photometry',
    'handling_habituation',
    'Imaging',
]

PROJECTS = [
    'ibl_neuropixel_brainwide_01',
    'practice'
]

GUI_DIR = Path(BASE_DIR).joinpath('iblrig', 'gui')
WIZARD_PNG = str(GUI_DIR.joinpath('wizard.png'))
ICON_FLUSH = str(GUI_DIR.joinpath('icon_flush.svg'))
ICON_HELP = str(GUI_DIR.joinpath('icon_help.svg'))
ICON_STATUS_LED = str(GUI_DIR.joinpath('icon_status_led.svg'))


# this class gets called to get the path constructor utility to predict the session path
class EmptySession(BaseSession):
    protocol_name = 'empty'

    def _run(self):
        pass

    def start_hardware(self):
        pass


def _set_list_view_from_string_list(ui_list: QtWidgets.QListView, string_list: list):
    """Small boiler plate util to set the selection of a list view from a list of strings"""
    if string_list is None or len(string_list) == 0:
        return
    for i, s in enumerate(ui_list.model().stringList()):
        if s in string_list:
            ui_list.selectionModel().select(ui_list.model().createIndex(i, 0), QtCore.QItemSelectionModel.Select)


@dataclass
class RigWizardModel:
    one: Optional[ONE] = None
    procedures: Optional[list] = None
    projects: Optional[list] = None
    task_name: Optional[str] = None
    user: Optional[str] = None
    subject: Optional[str] = None
    session_folder: Optional[Path] = None
    hardware_settings: Optional[dict] = None
    test_subject_name: Optional[str] = 'test_subject'
    subject_details_worker = None
    subject_details: Optional[tuple] = None

    def __post_init__(self):
        self.iblrig_settings = iblrig.path_helper.load_settings_yaml()
        self.all_users = [self.iblrig_settings['ALYX_USER']] if self.iblrig_settings['ALYX_USER'] else []
        self.all_procedures = sorted(PROCEDURES)

        # for the tasks, we build a dictionary that contains the task name as key and the path to task.py as value
        tasks = sorted([p for p in Path(iblrig_tasks.__file__).parent.rglob('task.py')])
        if CUSTOM_TASKS:
            tasks.extend(sorted([p for p in Path(iblrig_custom_tasks.__file__).parent.rglob('task.py')]))
        self.all_tasks = OrderedDict({p.parts[-2]: p for p in tasks})

        self.all_projects = sorted(PROJECTS)

        # get the subjects from iterating over folders in the the iblrig data path
        if self.iblrig_settings['iblrig_local_data_path'] is None:
            self.all_subjects = [self.test_subject_name]
        else:
            folder_subjects = Path(
                self.iblrig_settings['iblrig_local_data_path']).joinpath(
                self.iblrig_settings['ALYX_LAB'], 'Subjects')
            self.all_subjects = [self.test_subject_name] + sorted(
                [f.name for f in folder_subjects.glob('*') if f.is_dir() and f.name != self.test_subject_name])
        file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
        self.hardware_settings = yaml.safe_load(file_settings.read_text())

    def get_task_extra_parser(self, task_name=None):
        """
        Get the extra kwargs from the task, by importing the task and parsing the extra_parser static method
        This parser will give us a list of arguments and their types so we can build a custom dialog for this task
        :return:
        """
        assert task_name
        spec = importlib.util.spec_from_file_location("task", self.all_tasks[task_name])
        task = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = task
        spec.loader.exec_module(task)
        return task.Session.extra_parser()

    def connect(self, username=None, one=None):
        if one is None:
            username = username or self.iblrig_settings['ALYX_USER']
            self.one = ONE(base_url=self.iblrig_settings['ALYX_URL'], username=username, mode='local')
        else:
            self.one = one
        rest_subjects = self.one.alyx.rest('subjects', 'list', alive=True, stock=False,
                                           lab=self.iblrig_settings['ALYX_LAB'])
        self.all_subjects.remove(self.test_subject_name)
        self.all_subjects = sorted(
            set(self.all_subjects + [s['nickname'] for s in rest_subjects]))
        self.all_subjects = [self.test_subject_name] + self.all_subjects
        self.all_users = sorted(
            set([s['responsible_user'] for s in rest_subjects] + self.all_users))
        rest_projects = self.one.alyx.rest('projects', 'list')
        projects = [p['name'] for p in rest_projects if (username in p['users'] or len(p['users']) == 0)]
        self.all_projects = sorted(set(projects + self.all_projects))

    def get_subject_details(self, subject):
        self.subject_details_worker = SubjectDetailsWorker(subject)
        self.subject_details_worker.finished.connect(self.process_subject_details)
        self.subject_details_worker.start()

    def process_subject_details(self):
        self.subject_details = SubjectDetailsWorker.result


class RigWizard(QtWidgets.QMainWindow, Ui_wizard):
    def __init__(self, *args, **kwargs):
        super(RigWizard, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(WIZARD_PNG))

        self.settings = QtCore.QSettings()
        self.move(self.settings.value("pos", self.pos(), QtCore.QPoint))

        self.model = RigWizardModel()
        self.model2view()

        # default to biasedChoiceWorld
        if (idx := self.uiComboTask.findText('_iblrig_tasks_biasedChoiceWorld')) >= 0:
            self.uiComboTask.setCurrentIndex(idx)

        # connect widgets signals to slots
        self.uiComboTask.currentTextChanged.connect(self.controls_for_extra_parameters)
        self.uiComboSubject.currentTextChanged.connect(self.model.get_subject_details)
        self.uiPushHelp.clicked.connect(self.help)
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushStart.clicked.connect(self.start_stop)
        self.uiPushPause.clicked.connect(self.pause)
        self.uiListProjects.clicked.connect(self.enable_UI_elements)
        self.uiListProcedures.clicked.connect(self.enable_UI_elements)
        self.uiPushConnect.clicked.connect(self.alyx_connect)
        self.lineEditSubject.textChanged.connect(self._filter_subjects)

        self.uiPushStatusLED.setChecked(self.settings.value("bpod_status_led", True, bool))
        self.uiPushStatusLED.toggled.connect(self.toggle_status_led)
        self.toggle_status_led(self.uiPushStatusLED.isChecked())

        self.running_task_process = None
        self.task_arguments = dict()
        self.task_settings_widgets = None

        self.uiPushStart.installEventFilter(self)
        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.uiPushPause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.uiPushFlush.setIcon(QtGui.QIcon(ICON_FLUSH))
        self.uiPushHelp.setIcon(QtGui.QIcon(ICON_HELP))
        self.uiPushStatusLED.setIcon(QtGui.QIcon(ICON_STATUS_LED))

        self.controller2model()

        self.checkSubProcessTimer = QtCore.QTimer()
        self.checkSubProcessTimer.timeout.connect(self.check_sub_process)

        # display disk stats
        local_data = self.model.iblrig_settings['iblrig_local_data_path']
        local_data = Path(local_data) if local_data else Path.home().joinpath('iblrig_data')
        v8data_size = sum(file.stat().st_size for file in Path(local_data).rglob('*'))
        total_space, total_used, total_free = shutil.disk_usage(local_data.anchor)
        self.uiProgressDiskSpace.setStatusTip(f'utilization of drive {local_data.anchor}')
        self.uiProgressDiskSpace.setValue(round(total_used / total_space * 100))
        self.uiLabelDiskAvailableValue.setText(f'{total_free / 1024 ** 3 : .1f} GB')
        self.uiLabelDiskIblrigValue.setText(f'{v8data_size / 1024 ** 3 : .1f} GB')

        tmp = QtWidgets.QLabel(f'iblrig v{iblrig.__version__}')
        tmp.setContentsMargins(4, 0, 0, 0)
        self.statusbar.addWidget(tmp)
        self.controls_for_extra_parameters()

        self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowFullscreenButtonHint)

        # get AnyDesk ID
        # anydesk_worker = Worker(get_anydesk_id)
        # anydesk_worker.signals.result.connect(lambda var: print(f'Your AnyDesk ID: {var:s}'))
        # QThreadPool.globalInstance().tryStart(anydesk_worker)

        # check for update
        update_worker = Worker(check_for_updates)
        update_worker.signals.result.connect(self._on_check_update_result)
        QThreadPool.globalInstance().start(update_worker)

        # check dirty state
        dirty_worker = Worker(is_dirty)
        dirty_worker.signals.result.connect(self._on_check_dirty_result)
        QThreadPool.globalInstance().start(dirty_worker)

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
            msg_box.setDetailedText("To list all files that have been changed locally:\n\n"
                                    "    git diff --name-only\n\n"
                                    "To reset the repository to its default state:\n\n"
                                    "    git reset --hard")
            msg_box.exec()

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
            self.settings.setValue("pos", self.pos())
            self.settings.setValue("bpod_status_led", self.uiPushStatusLED.isChecked())
            self.toggle_status_led(is_toggled=True)
            bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])  # bpod is a singleton
            bpod.close()
            event.accept()

        if self.running_task_process is None:
            accept()
        else:
            msg_box = QtWidgets.QMessageBox(parent=self)
            msg_box.setWindowTitle("Hold on")
            msg_box.setText("A task is running - do you really want to quit?")
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
        self.uiComboUser.setModel(QtCore.QStringListModel(self.model.all_users))
        self.uiComboTask.setModel(QtCore.QStringListModel(list(self.model.all_tasks.keys())))
        self.uiComboSubject.setModel(QtCore.QStringListModel(self.model.all_subjects))
        self.uiListProcedures.setModel(QtCore.QStringListModel(self.model.all_procedures))
        self.uiListProjects.setModel(QtCore.QStringListModel(self.model.all_projects))
        # set the selections
        self.uiComboUser.setCurrentText(self.model.user)
        self.uiComboTask.setCurrentText(self.model.task_name)
        self.uiComboSubject.setCurrentText(self.model.subject)
        _set_list_view_from_string_list(self.uiListProcedures, self.model.procedures)
        _set_list_view_from_string_list(self.uiListProjects, self.model.projects)
        self.enable_UI_elements()

    def controller2model(self):
        self.model.procedures = [i.data() for i in self.uiListProcedures.selectedIndexes()]
        self.model.projects = [i.data() for i in self.uiListProjects.selectedIndexes()]
        self.model.task_name = self.uiComboTask.currentText()
        self.model.user = self.uiComboUser.currentText()
        self.model.subject = self.uiComboSubject.currentText()

    def controls_for_extra_parameters(self):
        self.controller2model()
        self.task_arguments = dict()

        # collect & filter list of parser arguments (general & task specific)
        args = sorted(_get_task_argument_parser()._actions, key=lambda x: x.dest)
        args = [x for x in args
                if not any(set(x.option_strings).intersection(['--subject', '--user', '--projects', '--log-level',
                                                               '--procedures', '--weight', '--help', '--append',
                                                               '--no-interactive', '--stub', '--wizard']))]
        args = sorted(self.model.get_task_extra_parser(self.model.task_name)._actions, key=lambda x: x.dest) + args

        group = self.uiGroupTaskParameters
        layout = group.layout()
        self.task_settings_widgets = [None] * len(args)

        while layout.rowCount():
            layout.removeRow(0)

        for idx, arg in enumerate(args):
            param = max(arg.option_strings, key=len)
            label = param.replace('_', ' ').replace('--', '').title()

            # create widget for bool arguments
            if isinstance(arg, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
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
                    widget.currentTextChanged.connect(
                        lambda val, p=param: self._set_task_arg(p, val))
                    widget.currentTextChanged.emit(widget.currentText())

                else:
                    widget = QtWidgets.QLineEdit()
                    if arg.default:
                        widget.setText(arg.default)
                    widget.editingFinished.connect(
                        lambda p=param, w=widget: self._set_task_arg(p, w.text()))
                    widget.editingFinished.emit()

            # create widget for list of floats
            elif arg.type == float and arg.nargs == '+':
                widget = QtWidgets.QLineEdit()
                if arg.default:
                    widget.setText(str(arg.default)[1:-1])
                widget.editingFinished.connect(
                    lambda p=param, w=widget:
                    self._set_task_arg(p, [x.strip() for x in w.text().split(',')]))
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
                widget.valueChanged.connect(
                    lambda val, p=param: self._set_task_arg(p, str(val)))
                widget.valueChanged.emit(widget.value())

            # no other argument types supported for now
            else:
                continue

            # add custom widget properties
            QtCore.QMetaProperty
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
                        lambda val, a=arg, m=widget.minimum():
                        self._set_task_arg(a.option_strings[0], str(val if val > m else -1)))
                    widget.valueChanged.emit(widget.value())

                case 'adaptive_gain':
                    label = 'Stimulus Gain, μl'
                    widget.setSpecialValueText('automatic')
                    widget.setMaximum(3)
                    widget.setSingleStep(0.1)
                    widget.setMinimum(1.4)
                    widget.setValue(widget.minimum())
                    widget.valueChanged.connect(
                        lambda val, a=arg, m=widget.minimum():
                        self._set_task_arg(a.option_strings[0], str(val if val > m else -1)))
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
        self.model.connect()
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
                self.enable_UI_elements()

                dlg = QtWidgets.QInputDialog()
                weight, ok = dlg.getDouble(self, 'Subject Weight', 'Subject Weight (g):', value=0, min=0,
                                           flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
                if not ok or weight == 0:
                    self.uiPushStart.setText('Start')
                    self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                    self.enable_UI_elements()
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
                cmd = [shutil.which('python')]
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
                for key in self.task_arguments.keys():
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
                    # self.running_task_process = QProcess()
                    # self.running_task_process.start(shutil.which('python'), cmd)
                    # self.running_task_process.readyReadStandardOutput.connect(self.handle_stdout)
                    # self.running_task_process.readyReadStandardError.connect(self.handle_stderr)
                    self.running_task_process = subprocess.Popen(cmd)
                self.uiPushStart.setStatusTip('stop the session after the current trial')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
                self.checkSubProcessTimer.start(1000)
            case 'Stop':
                self.uiPushStart.setText('Stop')
                self.checkSubProcessTimer.stop()
                # if the process crashed catastrophically, the session folder might not exist
                if self.model.session_folder and self.model.session_folder.exists():
                    self.model.session_folder.joinpath('.stop').touch()

                # this will wait for the process to finish, usually the time for the trial to end
                self.running_task_process.communicate()
                if self.running_task_process.returncode:
                    msgBox = QtWidgets.QMessageBox(parent=self)
                    msgBox.setWindowTitle("Oh no!")
                    msgBox.setText("The task was terminated with an error.\nPlease check the command-line output for details.")
                    msgBox.setIcon(QtWidgets.QMessageBox().Critical)
                    msgBox.exec_()

                self.running_task_process = None
                self.uiPushStart.setText('Start')
                self.uiPushStart.setStatusTip('start the session')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

                # re-enable UI elements and recall state of Bpod status LED
                self.enable_UI_elements()
                bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])
                bpod.set_status_led(self.uiPushStatusLED.isChecked())

                if (task_settings_file := Path(self.model.raw_data_folder).joinpath("_iblrig_taskSettings.raw.json")).exists():
                    with open(task_settings_file, "r") as fid:
                        session_data = json.load(fid)

                    # check if session was a dud
                    if (ntrials := session_data['NTRIALS']) < 42 and 'spontaneous' not in self.model.task_name:
                        answer = QtWidgets.QMessageBox.question(self, 'Is this a dud?',
                                                                f"The session consisted of only {ntrials:d} trial"
                                                                f"{'s' if ntrials>1 else ''} and appears to be a dud.\n\n"
                                                                f"Should it be deleted?")
                        if answer == QtWidgets.QMessageBox.Yes:
                            shutil.rmtree(self.model.session_folder)
                            return

                    # manage poop count
                    dlg = QtWidgets.QInputDialog()
                    droppings, ok = dlg.getInt(self, 'Droppings', 'Number of droppings:', value=0, min=0,
                                               flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
                    session_data['POOP_COUNT'] = droppings
                    with open(task_settings_file, "w") as fid:
                        json.dump(session_data, fid, indent=4, sort_keys=True, default=str)

    def check_sub_process(self):
        return_code = None if self.running_task_process is None else self.running_task_process.poll()
        if return_code is None:
            return
        else:
            self.start_stop()

    def flush(self):

        # paint button blue when in toggled state
        self.uiPushFlush.setStyleSheet('QPushButton {background-color: rgb(128, 128, 255);}'
                                       if self.uiPushFlush.isChecked() else '')
        self.enable_UI_elements()

        try:
            bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])  # bpod is a singleton
            bpod.manual_override(bpod.ChannelTypes.OUTPUT, bpod.ChannelNames.VALVE, 1, self.uiPushFlush.isChecked())
        except (OSError, exceptions.bpod_error.BpodErrorException):
            print(traceback.format_exc())
            print("Cannot find bpod - is it connected?")
            self.uiPushFlush.setChecked(False)
            self.uiPushFlush.setStyleSheet('')
            return

    def toggle_status_led(self, is_toggled: bool):

        # paint button green when in toggled state
        self.uiPushStatusLED.setStyleSheet('QPushButton {background-color: rgb(128, 255, 128);}'
                                           if is_toggled else '')
        self.enable_UI_elements()

        try:
            bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])
            bpod.set_status_led(is_toggled)
        except (OSError, exceptions.bpod_error.BpodErrorException, AttributeError):
            self.uiPushStatusLED.setChecked(False)
            self.uiPushStatusLED.setStyleSheet('')

    def help(self):
        webbrowser.open('https://int-brain-lab.github.io/iblrig/usage.html')

    def enable_UI_elements(self):
        is_running = self.uiPushStart.text() == 'Stop'

        self.uiPushStart.setEnabled(
            not self.uiPushFlush.isChecked()
            and len(self.uiListProjects.selectedIndexes()) > 0
            and len(self.uiListProcedures.selectedIndexes()) > 0)
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

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
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
        super(Worker, self).__init__()
        self.fn: Callable[..., Any] = fn
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
        except:  # noqa: 722
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
        self.setWindowIcon(QtGui.QIcon(WIZARD_PNG))
        self.uiLabelLogo.setPixmap(QtGui.QPixmap(WIZARD_PNG))
        self.uiLabelHeader.setText(f"Update to iblrig {version} is available.")
        self.uiTextBrowserChanges.setMarkdown(get_changelog())
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.exec()


class SubjectDetailsWorker(QThread):
    subject_name: Union[str, None] = None
    result: Union[tuple[dict, dict], None] = None

    def __init__(self, subject_name):
        super().__init__()
        self.subject_name = subject_name

    def run(self):
        self.result = get_subject_training_info(self.subject_name)


def main():
    QtCore.QCoreApplication.setOrganizationName("International Brain Laboratory")
    QtCore.QCoreApplication.setOrganizationDomain("internationalbrainlab.org")
    QtCore.QCoreApplication.setApplicationName("IBLRIG Wizard")

    if os.name == 'nt':
        app_id = f'IBL.iblrig.wizard.{iblrig.__version__}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    w = RigWizard()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
