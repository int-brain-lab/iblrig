from collections import OrderedDict
import importlib
from pathlib import Path
import shutil
import subprocess
import signal
import sys

from PyQt5 import QtWidgets, QtCore, uic

from one.api import ONE
import iblrig_tasks
import iblrig_custom_tasks
import iblrig.path_helper

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


class RigWizardModel():

    def __init__(self):
        self.one = None
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

    def connect(self):
        # todo get username
        self.one = ONE(base_url=self.iblrig_settings['ALYX_URL'], username=self.iblrig_settings['ALYX_USER'])
        rest_subjects = self.one.alyx.rest('subjects', 'list', alive=True, lab=self.iblrig_settings['ALYX_LAB'])
        self.all_subjects = sorted(set(self.all_subjects + [s['nickname'] for s in rest_subjects]))
        self.all_users = sorted(set([s['responsible_user'] for s in rest_subjects] + self.all_users))
        # self.one.alyx.rest('projects', 'list')


class RigWizard(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(RigWizard, self).__init__(*args, **kwargs)
        uic.loadUi(Path(__file__).parent.joinpath('wizard.ui'), self)
        self.settings = QtCore.QSettings('iblrig', 'wizard')
        self.model = RigWizardModel()
        self.model2view()
        self.uiPushStart.clicked.connect(self.startstop)
        self.uiPushConnect.clicked.connect(self.alyx_connect)
        self.running_task_process = None

    def model2view(self):
        self.uiComboUser.setModel(QtCore.QStringListModel(self.model.all_users))
        self.uiComboTask.setModel(QtCore.QStringListModel(list(self.model.all_tasks.keys())))
        self.uiComboSubject.setModel(QtCore.QStringListModel(self.model.all_subjects))
        self.uiListProcedures.setModel(QtCore.QStringListModel(self.model.all_procedures))
        self.uiListProjects.setModel(QtCore.QStringListModel(self.model.all_projects))

    def alyx_connect(self):
        self.model.connect()
        self.model2view()

    def startstop(self):
        match self.uiPushStart.text():
            case 'Start':
                # getting the current state of the view is a controller2model future method
                procedures = [i.data() for i in self.uiListProcedures.selectedIndexes()]
                projects = [i.data() for i in self.uiListProjects.selectedIndexes()]
                task_name = self.uiComboTask.currentText()
                user = self.uiComboUser.currentText()
                subject = self.uiComboSubject.currentText()
                # runs the python command
                cmd = [shutil.which('python'), str(self.model.all_tasks[task_name]), '--user', user, '--subject', subject]
                if procedures:
                    cmd.extend(['--procedures', ' '.join(procedures)])
                if projects:
                    cmd.extend(['--projects', ' '.join(projects)])
                if self.running_task_process is None:
                    self.running_task_process = subprocess.Popen(cmd)
                self.uiPushStart.setText('Stop')
            case 'Stop':
                # ideally here I would know the session folder and stop the session by writing the stop file with no SIGINT
                self.running_task_process.send_signal(signal.SIGINT)
                self.running_task_process.communicate()
                self.running_task_process = None
                self.uiPushStart.setText('Start')


def main():
    app = QtWidgets.QApplication([])
    w = RigWizard()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()
