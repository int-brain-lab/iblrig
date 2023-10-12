from collections import OrderedDict
from dataclasses import dataclass
import importlib
import json
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import yaml
import traceback
import webbrowser
import ctypes
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QStyle

from one.api import ONE
import iblrig_tasks
import iblrig_custom_tasks
import iblrig.path_helper
from iblrig.constants import BASE_DIR
from iblrig.misc import _get_task_argument_parser
from iblrig.base_tasks import BaseSession
from iblrig.hardware import Bpod
from iblrig.version_management import check_for_updates, get_changelog, is_dirty
from iblrig.gui.ui_wizard import Ui_wizard
from iblrig.gui.ui_update import Ui_update
from iblrig.choiceworld import get_subject_training_info
from pybpodapi import exceptions

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

WIZARD_PNG = str(Path(BASE_DIR).joinpath('iblrig', 'gui', 'wizard.png'))


# this class gets called to get the path constructor utility to predict the session path
class EmptySession(BaseSession):
    protocol_name = 'empty'

    def _run(self):
        pass

    def start_hardware(self):
        pass


def _set_list_view_from_string_list(uilist: QtWidgets.QListView, string_list: list):
    """Small boiler plate util to set the selection of a list view from a list of strings"""
    if string_list is None or len(string_list) == 0:
        return
    for i, s in enumerate(uilist.model().stringList()):
        if s in string_list:
            uilist.selectionModel().select(uilist.model().createIndex(i, 0), QtCore.QItemSelectionModel.Select)


@dataclass
class RigWizardModel:
    one: ONE = None
    procedures: list = None
    projects: list = None
    task_name: str = None
    user: str = None
    subject: str = None
    session_folder: Path = None
    hardware_settings: dict = None
    test_subject_name: str = 'test_subject'
    subject_details_worker = None
    subject_details: tuple = None

    def __post_init__(self):
        self.iblrig_settings = iblrig.path_helper.load_settings_yaml()
        self.all_users = [self.iblrig_settings['ALYX_USER']] if self.iblrig_settings['ALYX_USER'] else []
        self.all_procedures = sorted(PROCEDURES)
        # for the tasks, we build a dictionary that contains the task name as key and the path to the task.py as value
        tasks = sorted([p for p in Path(iblrig_tasks.__file__).parent.rglob('task.py')])
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

        self.settings = QtCore.QSettings('iblrig', 'wizard')
        self.model = RigWizardModel()
        self.model2view()

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

        self.running_task_process = None
        self.task_arguments = dict()
        self.task_settings_widgets = None

        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.uiPushStart.installEventFilter(self)

        self.uiPushPause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.uiPushFlush.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.uiPushHelp.setIcon(self.style().standardIcon(QStyle.SP_DialogHelpButton))

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

        self.update_check = UpdateCheckWorker(self)

        QtCore.QTimer.singleShot(100, self.check_dirty)

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

    def closeEvent(self, event):
        if self.running_task_process is None:
            event.accept()
        else:
            msgBox = QtWidgets.QMessageBox(parent=self)
            msgBox.setWindowTitle("Hold on")
            msgBox.setText("A task is running - do you really want to quit?")
            msgBox.setStandardButtons(QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Yes)
            msgBox.setIcon(QtWidgets.QMessageBox().Question)
            match msgBox.exec_():
                case QtWidgets.QMessageBox.No:
                    event.ignore()
                case QtWidgets.QMessageBox.Yes:
                    self.setEnabled(False)
                    self.repaint()
                    self.start_stop()
                    event.accept()

    def check_dirty(self):
        """
        Check if the iblrig installation contains local changes.

        This method checks if the installed version of iblrig contains local changes
        (indicated by the version string ending with 'dirty'). If local changes are
        detected, it displays a warning message to inform the user about potential
        issues and provides instructions on how to reset the repository to its
        default state.

        Returns
        -------
        None
        """
        if not is_dirty():
            return
        msg_box = QtWidgets.QMessageBox(parent=self)
        msg_box.setWindowTitle("Warning")
        msg_box.setText("Your copy of iblrig contains local changes.\nDon't expect things to work as intended!")
        msg_box.setDetailedText("To reset the repository to its default state, use:\n\n    git reset --hard\n\n")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.setIcon(QtWidgets.QMessageBox().Information)
        msg_box.exec_()

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
                widget.toggled.connect(lambda val, p=param: self._set_task_arg(param, val > 0))
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
                    cmd.extend([key, self.task_arguments[key]])
                cmd.extend(['--weight', f'{weight}'])
                cmd.append('--wizard')
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                if self.running_task_process is None:
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
                self.enable_UI_elements()

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

        if not self.uiPushFlush.isChecked():
            bpod.close()

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
        self.uiCheckAppend.setEnabled(not is_running)
        self.uiGroupParameters.setEnabled(not is_running)
        self.uiGroupTaskParameters.setEnabled(not is_running)
        self.uiGroupTools.setEnabled(not is_running)
        self.repaint()


class UpdateCheckWorker(QThread):
    """
    A worker thread for checking updates and displaying update notices.

    This class is used to run the update check in a separate thread to avoid
    blocking the main UI. When the update check is completed, it triggers the
    display of an update notice if an update is available.

    Parameters
    ----------
    parent : QtWidgets.QWidget
        The parent widget associated with this worker.

    Attributes
    ----------
    update_available : bool
        A flag indicating whether an update is available.

    remote_version : str
        The remote version of the application.

    Methods
    -------
    run() -> None
        The main method that performs the update check and sets the result.

    check_results() -> None
        A method that is called when the update check is finished to show
        an update notice if an update is available.
    """

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__()
        self.parent = parent
        self.update_available = False
        self.remote_version = ''
        self.finished.connect(self.check_results)
        self.start()

    def run(self) -> None:
        """
        Perform the update check and set the result.

        This method is automatically called when the worker thread is started.
        It runs the update check by calling check_for_updates() and sets
        the update_available and remote_version attributes based on the result.
        """
        self.update_available, self.remote_version = check_for_updates()

    def check_results(self) -> None:
        """
        Check the update check results and display an update notice if available.

        This method is called when the update check is finished. It checks if
        an update is available, and if so, it displays an update notice dialog.
        """
        if self.update_available:
            self.UpdateNotice(parent=self.parent, version=self.remote_version)

    class UpdateNotice(QtWidgets.QDialog, Ui_update):
        """
        A dialog for displaying update notices.

        This class is used to create a dialog for displaying update notices.
        It shows information about the available update and provides a changelog.

        Parameters
        ----------
        parent : QtWidgets.QWidget
            The parent widget associated with this dialog.

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
            self.exec_()


class SubjectDetailsWorker(QThread):
    subject_name: str = None
    result: tuple[dict, dict] = None

    def __init__(self, subject_name):
        super().__init__()
        self.subject_name = subject_name

    def run(self):
        self.result = get_subject_training_info(self.subject_name)


def main():
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
