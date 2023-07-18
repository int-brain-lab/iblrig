import unittest

from one.api import ONE
from ibllib.tests import TEST_DB

from iblrig.gui.wizard import RigWizardModel, PROJECTS


class TestRigWizardModel(unittest.TestCase):

    def setUp(self):
        self.wizard = RigWizardModel()
        self.wizard.one = ONE(**TEST_DB, mode='remote')

    def test_connect(self):
        self.wizard.connect()
        assert len(self.wizard.all_projects) > len(PROJECTS)

    def test_get_task_extra_kwargs(self):
        """
        This is a test that gets quite a bit of coverage as it will import all of the tasks
        from the iblrig_tasks package and run a static method that returns the variable number of input prompts for each
        :return:
        """
        for task_name in self.wizard.all_tasks:
            extra_args = self.wizard._get_task_extra_kwargs(task_name)
            match task_name:
                case '_iblrig_tasks_ephysChoiceWorld':
                    assert len(extra_args) == 2
                case '_iblrig_tasks_trainingChoiceWorld':
                    assert len(extra_args) == 1
                case _:
                    assert len(extra_args) == 0
