from pathlib import Path

import numpy as np
from one.api import ONE
import iblrig
import iblrig.path_helper

from PyQt5 import QtWidgets, QtCore, uic

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
        self.all_tasks = sorted([p.parts[-2] for p in Path(iblrig.__file__).parents[1].joinpath('iblrig_tasks').rglob('task.py')])
        self.all_projects = sorted(PROJECTS)
        # get the subjects from iterating over folders in the the iblrig data path
        if self.iblrig_settings['iblrig_local_data_path'] is None:
            self.all_subjects = []
        else:
            folder_subjects = Path(
                self.iblrig_settings['iblrig_local_data_path']).joinpath(
                self.iblrig_settings['ALYX_LAB'], 'Subjects')
            self.all_subjects = sorted([f.name for f in folder_subjects.glob('*') if f.is_dir()])

    # def connect(self):
    #     self.one = ONE(base_url=self.iblrig_settings['ALYX_URL'], username=self.username)
    #     rest_subjects = self.one.alyx.rest('subjects', 'list', alive=True, lab=self.iblrig_settings['ALYX_LAB'])

        # projects = np.unique(np.concatenate([s['projects'] for s in rest_subjects if s['projects']]))
        # subjects = np.sort([s['nickname'] for s in rest_subjects])
        # procedures = np.sort(PROCEDURES)


class RigWizard(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(RigWizard, self).__init__(*args, **kwargs)
        uic.loadUi(Path(__file__).parent.joinpath('wizard.ui'), self)
        self.settings = QtCore.QSettings('iblrig', 'wizard')
        self.model = RigWizardModel()
        self.update_view_fixtures()
        self.uiPushStart.clicked.connect(self.start)

    def update_view_fixtures(self):
        self.uiComboUser.setModel(QtCore.QStringListModel(self.model.all_users))
        self.uiComboTask.setModel(QtCore.QStringListModel(self.model.all_tasks))
        self.uiComboSubject.setModel(QtCore.QStringListModel(self.model.all_subjects))
        self.uiListProcedures.setModel(QtCore.QStringListModel(self.model.all_procedures))
        self.uiListProjects.setModel(QtCore.QStringListModel(self.model.all_projects))

    def start(self):
        a = 1


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    w = RigWizard()
    w.show()
    app.exec_()
