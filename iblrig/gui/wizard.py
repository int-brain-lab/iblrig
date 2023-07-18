from collections import OrderedDict
from dataclasses import dataclass
import importlib
from pathlib import Path
import shutil
import subprocess
import sys
import yaml

from PyQt5 import QtWidgets, QtCore, uic

from one.api import ONE
import iblrig_tasks
import iblrig_custom_tasks
import iblrig.path_helper
from iblrig.base_tasks import BaseSession
from iblrig.hardware import Bpod

PROCEDURES = [
    'Behavior training/tasks',
    'Ephys recording with acute probe(s)',
    'Ephys recording with chronic probe(s)',
    'Fiber photometry',
    'handling_habituation'
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
    bpod_found: bool = None

    def __post_init__(self):
        self.iblrig_settings = iblrig.path_helper.load_settings_yaml()
        self.all_users = [self.iblrig_settings['ALYX_USER']]
        self.all_procedures = sorted(PROCEDURES)
        # for the tasks, we build a dictionary that contains the task name as key and the path to the task.py as value
        tasks = sorted([p for p in Path(iblrig_tasks.__file__).parent.rglob('task.py')])
        tasks.extend(sorted([p for p in Path(iblrig_custom_tasks.__file__).parent.rglob('task.py')]))
        self.all_tasks = OrderedDict({p.parts[-2]: p for p in tasks})
        self.all_projects = sorted(PROJECTS)
        # get the subjects from iterating over folders in the the iblrig data path
        if self.iblrig_settings['iblrig_local_data_path'] is None:
            self.all_subjects = []
        else:
            folder_subjects = Path(
                self.iblrig_settings['iblrig_local_data_path']).joinpath(
                self.iblrig_settings['ALYX_LAB'], 'Subjects')
            self.all_subjects = sorted([f.name for f in folder_subjects.glob('*') if f.is_dir()])
        file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
        self.hardware_settings = yaml.safe_load(file_settings.read_text())
        self.bpod_found = Bpod(self.hardware_settings['device_bpod']['COM_BPOD']).is_connected

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

    def connect(self, username=None):
        username = username or self.iblrig_settings['ALYX_USER']
        # todo define new username
        self.one = ONE(base_url=self.iblrig_settings['ALYX_URL'], username=username, mode='local')
        rest_subjects = self.one.alyx.rest('subjects', 'list', alive=True, lab=self.iblrig_settings['ALYX_LAB'])
        self.all_subjects = sorted(set(self.all_subjects + [s['nickname'] for s in rest_subjects]))
        self.all_users = sorted(set([s['responsible_user'] for s in rest_subjects] + self.all_users))
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
        self.uiPushFlush.clicked.connect(self.flush)
        self.uiPushStart.clicked.connect(self.startstop)
        self.uiPushConnect.clicked.connect(self.alyx_connect)
        self.running_task_process = None
        if not self.model.bpod_found:
            self.uiPushFlush.setEnabled(False)

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

    def controller2model(self):
        self.model.procedures = [i.data() for i in self.uiListProcedures.selectedIndexes()]
        self.model.projects = [i.data() for i in self.uiListProjects.selectedIndexes()]
        self.model.task_name = self.uiComboTask.currentText()
        self.model.user = self.uiComboUser.currentText()
        self.model.subject = self.uiComboSubject.currentText()

    def alyx_connect(self):
        self.model.connect()
        self.model2view()

    def startstop(self):
        match self.uiPushStart.text():
            case 'Start':
                self.controller2model()
                task = EmptySession(subject=self.model.subject, append=self.uiCheckAppend.isChecked())
                self.model.session_folder = task.paths['SESSION_FOLDER']
                if self.model.session_folder.joinpath('.stop').exists():
                    self.model.session_folder.joinpath('.stop').unlink()
                # runs the python command
                cmd = [shutil.which('python'), str(self.model.all_tasks[self.model.task_name]),
                       '--user', self.model.user, '--subject', self.model.subject]
                if self.model.procedures:
                    cmd.extend(['--procedures', *self.model.procedures])
                if self.model.projects:
                    cmd.extend(['--projects', *self.model.projects])
                if self.uiCheckAppend.isChecked():
                    cmd.append('--append')
                if self.running_task_process is None:
                    self.running_task_process = subprocess.Popen(cmd)
                self.uiPushStart.setText('Stop')
                self.uiPushFlush.setEnabled(False)
            case 'Stop':
                # if the process crashed catastrophically, the session folder might not exist
                if self.model.session_folder.exists():
                    self.model.session_folder.joinpath('.stop').touch()
                # this will wait for the process to finish, usually the time for the trial to end
                self.running_task_process.communicate()
                self.running_task_process = None
                self.uiPushStart.setText('Start')
                self.uiPushFlush.setEnabled(True    )

    def flush(self):
        bpod = Bpod(self.model.hardware_settings['device_bpod']['COM_BPOD'])  # bpod is a singleton
        bpod.manual_override(bpod.ChannelTypes.OUTPUT, bpod.ChannelNames.VALVE, 1, self.uiPushFlush.isChecked())
        if self.uiPushFlush.isChecked():
            self.uiPushStart.setEnabled(False)
        else:
            bpod.close()
            self.uiPushStart.setEnabled(True)



def main():
    app = QtWidgets.QApplication([])
    w = RigWizard()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()
