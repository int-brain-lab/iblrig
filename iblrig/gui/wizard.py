from collections import OrderedDict
from dataclasses import dataclass
import importlib
from pathlib import Path
import shutil
import subprocess
import sys
import yaml
import traceback
import webbrowser

from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import QStyle

from one.api import ONE
import iblrig_tasks
import iblrig_custom_tasks
import iblrig.path_helper
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
        file_settings = Path(iblrig.__file__).parents[1].joinpath('settings',
                                                                  'hardware_settings.yaml')
        self.hardware_settings = yaml.safe_load(file_settings.read_text())

    def _get_task_extra_kwargs(self, task_name=None):
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
        return [{act.option_strings[0]: act.type} for act in task.Session.extra_parser()._actions]

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
        self.uiPushHelp.clicked.connect(self.help)
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushStart.clicked.connect(self.startstop)
        self.uiPushPause.clicked.connect(self.pause)
        self.uiPushConnect.clicked.connect(self.alyx_connect)
        self.lineEditSubject.textChanged.connect(self._filter_subjects)
        self.running_task_process = None
        self.setDisabled(True)

        self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.uiPushPause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.uiPushFlush.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.uiPushHelp.setIcon(self.style().standardIcon(QStyle.SP_DialogHelpButton))

        self.checkSubProcessTimer = QtCore.QTimer()
        self.checkSubProcessTimer.timeout.connect(self.checkSubProcess)

        self.statusbar.showMessage("Checking for updates ...")
        self.show()
        QtCore.QTimer.singleShot(1, self.check_for_update)

    def check_for_update(self):
        update_available, remote_version = check_for_updates()
        if update_available == 1:
            msgBox = QtWidgets.QMessageBox(parent=self)
            msgBox.setWindowTitle("Update Notice")
            msgBox.setText(f"Update toiblrig {remote_version} is available.")
            msgBox.setInformativeText("Please update using 'git pull'.")
            msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msgBox.setIcon(QtWidgets.QMessageBox().Information)
            msgBox.findChild(QtWidgets.QPushButton).setText('Yes, I promise!')
            msgBox.exec_()
        self.setDisabled(False)
        self.statusbar.showMessage(f"iblrig v{remote_version}")
        self.update()

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
                self.controller2model()
                task = EmptySession(subject=self.model.subject, append=self.uiCheckAppend.isChecked(), wizard=True)
                self.model.session_folder = task.paths['SESSION_FOLDER']
                if self.model.session_folder.joinpath('.stop').exists():
                    self.model.session_folder.joinpath('.stop').unlink()
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
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                cmd.append('--wizard')
                if self.running_task_process is None:
                    self.running_task_process = subprocess.Popen(cmd)
                self.uiPushStart.setText('Stop')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
                self.checkSubProcessTimer.start(100)
            case 'Stop':
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
                self.uiPushStart.setText('Start')
                self.uiPushStart.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.enable_UI_elements()

    def checkSubProcess(self):
        returncode = None if self.running_task_process is None else self.running_task_process.poll()
        if returncode is None:
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
            return

        if not self.uiPushFlush.isChecked():
            bpod.close()

    def help(self):
        webbrowser.open('https://int-brain-lab.github.io/iblrig/usage.html')

    def enable_UI_elements(self):
        is_running = self.uiPushStart.text() == 'Stop'

        self.uiPushStart.setEnabled(
            not self.uiPushFlush.isChecked())
        self.uiPushPause.setEnabled(is_running)
        self.uiPushFlush.setEnabled(not is_running)
        self.uiCheckAppend.setEnabled(not is_running)
        self.uiGroupUser.setEnabled(not is_running)
        self.uiGroupSubject.setEnabled(not is_running)
        self.uiGroupTask.setEnabled(not is_running)
        self.uiGroupProjects.setEnabled(not is_running)
        self.uiGroupProcedures.setEnabled(not is_running)
        self.repaint()


def main():
    app = QtWidgets.QApplication([])
    app.setStyle("Fusion")
    w = RigWizard()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()
