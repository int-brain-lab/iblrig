import unittest
from iblrig.gui.wizard import RigWizardModel


class TestRigWizardModel(unittest.TestCase):

    def setUp(self):
        self.wizard = RigWizardModel()

    def test_get_task_extra_kwargs(self):
        """
        This is a good test as it will import all of the tasks from the iblrig_tasks package and
        run a static method that returns the variable number of input prompts for each task.
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
