from PyQt5 import QtWidgets, QtCore, uic, QtGui
from iblrig.gui.wizard import RigWizard


QT_APP = QtWidgets.QApplication.instance()
if QT_APP is None:  # pragma: no cover
    QT_APP = QtWidgets.QApplication([])

self = RigWizard()
self.show()

## get the list selection

procedures = [i.data() for i in self.uiListProcedures.selectedIndexes()]
projects = [i.data() for i in self.uiListProjects.selectedIndexes()]
task = self.uiComboTask.currentText()
user = self.uiComboUser.currentText()
subject = self.uiComboSubject.currentText()

from pathlib import Path
import iblrig
import subprocess
import shutil
task_file = Path(iblrig.__file__).parents[1].joinpath('iblrig_tasks', task, 'task.py')

cmd = [shutil.which('python'), str(task_file), '--user', user, '--subject', subject]
if procedures:
    cmd.extend(['--procedures', ' '.join(procedures)])
if projects:
    cmd.extend(['--projects', ' '.join(projects)])

import sys
proc = subprocess.Popen(cmd, stdin=sys.stdin)
# selectionChanged is the callback name, addItem(), addItems() is the function to add
# self.uiListProcedures.takeItem()
# self.uiListProjects.selectionChanged()
# todo set the list selection

# get/set combo box selections
# self.uiComboTask.currentIndex()
# self.uiComboTask.setCurrentIndex(3)
# self.uiComboTask.currentIndexChanged
# self.uiComboTask.addItem()
# self.uiComboTask.addItems()
# self.uiComboUser.removeItem()

