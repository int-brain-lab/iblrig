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
from random import choice

from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import QStyle

from one.api import ONE
import iblrig_tasks
import iblrig_custom_tasks
import iblrig.path_helper
from iblrig.misc import _get_task_argument_parser
from iblrig.base_tasks import BaseSession
from iblrig.hardware import Bpod
from iblrig.version_management import check_for_updates
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


class RigWizard(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(RigWizard, self).__init__(*args, **kwargs)
        uic.loadUi(Path(__file__).parent.joinpath('wizard.ui'), self)
        self.settings = QtCore.QSettings('iblrig', 'wizard')
        self.model = RigWizardModel()
        self.model2view()

        self.uiComboTask.currentIndexChanged.connect(self.controls_for_extra_parameters)
        self.uiPushHelp.clicked.connect(self.help)
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushStart.clicked.connect(self.startstop)
        self.uiPushPause.clicked.connect(self.pause)
        self.uiListProjects.clicked.connect(self.enable_UI_elements)
        self.uiListProcedures.clicked.connect(self.enable_UI_elements)
        self.uiPushConnect.clicked.connect(self.alyx_connect)
        self.lineEditSubject.textChanged.connect(self._filter_subjects)
        self.running_task_process = None
        self.taskArguments = dict()
        self.taskSettingsWidgets = None

        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.uiPushPause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.uiPushFlush.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.uiPushHelp.setIcon(self.style().standardIcon(QStyle.SP_DialogHelpButton))

        self.controller2model()

        self.checkSubProcessTimer = QtCore.QTimer()
        self.checkSubProcessTimer.timeout.connect(self.checkSubProcess)

        # display disk stats
        local_data = self.model.iblrig_settings['iblrig_local_data_path']
        local_data = Path(local_data) if local_data else Path.home().joinpath('iblrig_data')
        v8data_size = sum(file.stat().st_size for file in Path(local_data).rglob('*'))
        total_space, total_used, total_free = shutil.disk_usage(local_data.anchor)
        self.uiProgressDiskSpace.setStatusTip(f'utilization of drive {local_data.anchor}')
        self.uiProgressDiskSpace.setValue(round(total_used / total_space * 100))
        self.uiLableDiskAvailableValue.setText(f'{total_free / 1024**3 : .1f} GB')
        self.uiLableDiskIblrigValue.setText(f'{v8data_size / 1024**3 : .1f} GB')

        tmp = QtWidgets.QLabel(f'iblrig v{iblrig.__version__}')
        tmp.setContentsMargins(4, 0, 0, 0)
        self.statusbar.addWidget(tmp)
        self.controls_for_extra_parameters()
        self.setDisabled(True)

        QtCore.QTimer.singleShot(1, self.check_dirty)
        QtCore.QTimer.singleShot(1, self.check_for_update)

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
                    self.startstop()
                    event.accept()

    def check_dirty(self):
        if not iblrig.__version__.endswith('dirty'):
            return
        msg_box = QtWidgets.QMessageBox(parent=self)
        msg_box.setWindowTitle("Warning")
        msg_box.setText("Your copy of iblrig contains local changes.\nDon't expect things to work as intended!")
        msg_box.setDetailedText("To reset the repository to its default state, use:\n\n    git reset --hard\n\n")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.setIcon(QtWidgets.QMessageBox().Information)
        msg_box.exec_()
        self.setDisabled(False)

    def check_for_update(self):
        self.statusbar.showMessage("Checking for updates ...")
        update_available, remote_version = check_for_updates()
        if update_available:
            cmdBox = QtWidgets.QLineEdit('upgrade_iblrig')
            cmdBox.setReadOnly(True)
            msgBox = QtWidgets.QMessageBox(parent=self)
            msgBox.setWindowTitle("Update Notice")
            msgBox.setText(f"Update to iblrig {remote_version} is available.\n\n"
                           f"Please update iblrig by issuing:")
            msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msgBox.setIcon(QtWidgets.QMessageBox().Information)
            msgBox.layout().addWidget(cmdBox, 1, 2)
            msgBox.findChild(QtWidgets.QPushButton).setText(
                choice(['Yes, I promise!', 'I will do so immediately!',
                        'Straight away!', 'Of course I will!']))
            msgBox.exec_()
        self.setDisabled(False)
        self.statusbar.clearMessage()

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
        self.taskArguments = dict()

        #
        args_general = sorted(_get_task_argument_parser()._actions, key=lambda x: x.dest)
        args_general = [x for x in args_general
                        if not any(set(x.option_strings).intersection(['--subject', '--user', '--projects',
                                                                       '--log-level', '--procedures', '--weight',
                                                                       '--help', '--append', '--no-interactive',
                                                                       '--stub']))]
        args_extra = sorted(self.model.get_task_extra_parser(self.model.task_name)._actions, key=lambda x: x.dest)
        args = args_extra + args_general

        group = self.uiGroupTaskParameters
        layout = group.layout()
        self.taskSettingsWidgets = [None] * len(args)

        while layout.rowCount():
            layout.removeRow(0)

        for idx, arg in enumerate(args):
            label = arg.option_strings[0]
            label = label.replace('_', ' ').replace('--', '').title()
            label = label.replace('Id', 'ID')
            param = arg.option_strings[0]

            if isinstance(arg, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                widget = QtWidgets.QCheckBox()
                widget.setTristate(False)
                if arg.default:
                    widget.setCheckState(arg.default * 2)
                widget.toggled.connect(lambda val, a=arg: self._set_task_arg(a.option_strings[0], val > 0))
                widget.toggled.emit(widget.isChecked() > 0)

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

            elif arg.type in [float, int]:
                if arg.type == float:
                    widget = QtWidgets.QDoubleSpinBox()
                    widget.setDecimals(1)
                else:
                    widget = QtWidgets.QSpinBox()
                if arg.default:
                    widget.setValue(arg.default)
                widget.valueChanged.connect(
                    lambda val, a=arg: self._set_task_arg(a.option_strings[0], str(val)))
                widget.valueChanged.emit(widget.value())

            else:
                continue

            # display help strings as status tip
            if arg.help:
                widget.setStatusTip(arg.help)

            if label == 'Training Phase':
                widget.setSpecialValueText('automatic')
                widget.setMaximum(5)
                widget.setMinimum(-1)
                widget.setValue(-1)

            layout.addRow(self.tr(label), widget)

        # add label to indicate absence of task specific parameters
        if layout.rowCount() == 0:
            layout.addRow(self.tr('(none)'), None)
            layout.itemAt(0, 0).widget().setEnabled(False)

        # call timer to set size of window
        QtCore.QTimer.singleShot(1, self.setSize)

    def _set_task_arg(self, key, value):
        self.taskArguments[key] = value

    def setSize(self):
        self.setFixedSize(self.layout().minimumSize())

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

    def startstop(self):
        match self.uiPushStart.text():
            case 'Start':
                self.uiPushStart.setText('Stop')
                self.enable_UI_elements()

                dlg = QtWidgets.QInputDialog()
                weight, ok = dlg.getDouble(self, 'Subject Weight', 'Subject Weight (g):', value=0, min=0,
                                           flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
                if not ok or weight == 0:
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
                for key in self.taskArguments.keys():
                    cmd.extend([key, self.taskArguments[key]])
                cmd.extend(['--weight', f'{weight}'])
                cmd.append('--no-interactive')
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                if self.running_task_process is None:
                    self.running_task_process = subprocess.Popen(cmd)
                self.uiPushStart.setStatusTip('stop the session after the current trial')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
                self.checkSubProcessTimer.start(1000)
            case 'Stop':
                self.uiPushStart.setText('Stop')
                self.uiPushStart.setEnabled(False)
                self.checkSubProcessTimer.stop()
                # if the process crashed catastrophically, the session folder might not exist
                if self.model.session_folder.exists():
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

                # manage poop count
                task_settings_file = Path(self.model.raw_data_folder).joinpath("_iblrig_taskSettings.raw.json")
                if task_settings_file.exists():
                    dlg = QtWidgets.QInputDialog()
                    droppings, ok = dlg.getInt(self, 'Droppings', 'Number of droppings:', value=0, min=0,
                                               flags=dlg.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
                    with open(task_settings_file, "r") as fid:
                        d = json.load(fid)
                    d['POOP_COUNT'] = droppings
                    with open(task_settings_file, "w") as fid:
                        json.dump(d, fid, indent=4, sort_keys=True, default=str)

                self.uiPushStart.setText('Start')
                self.uiPushStart.setStatusTip('start the session')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                self.enable_UI_elements()

    def checkSubProcess(self):
        return_code = None if self.running_task_process is None else self.running_task_process.poll()
        if return_code is None:
            return
        else:
            self.startstop()

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


def main():
    app = QtWidgets.QApplication([])
    app.setStyle("Fusion")
    w = RigWizard()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()
