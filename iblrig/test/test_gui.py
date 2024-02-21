import unittest
from unittest.mock import patch

from ibllib.tests import TEST_DB
from iblrig.constants import SETTINGS_PATH
from iblrig.gui.wizard import PROJECTS, RigWizardModel
from one.webclient import AlyxClient
from iblrig.hardware_validation import ValidateResult


class TestRigWizardModel(unittest.TestCase):
    def setUp(self):
        self.wizard = RigWizardModel(
            file_hardware_settings=SETTINGS_PATH.joinpath('hardware_settings_template.yaml'),
            file_iblrig_settings=SETTINGS_PATH.joinpath('iblrig_settings_template.yaml'),
        )

    @patch('iblrig.gui.wizard.iblrig.hardware_validation.ValidateAlyxLabLocation._run', return_value=ValidateResult('PASS'))
    def test_connect(self, mock_validate_alyx):
        self.wizard.login(username=TEST_DB['username'], alyx_client=AlyxClient(**TEST_DB))
        mock_validate_alyx.assert_called_once()
        assert len(self.wizard.all_projects) > len(PROJECTS)

    def test_get_task_extra_kwargs(self):
        """
        This is a test that gets quite a bit of coverage as it will import all of the tasks
        from the iblrig_tasks package and run a static method that returns the variable number of input prompts for each
        We only test the number of arguments for main iblrig tasks, not the custom tasks from project_extraction repo,
        but we still round-up and import the custom tasks
        :return:
        """
        for task_name in self.wizard.all_tasks:
            with self.subTest(task_name=task_name):
                parser = self.wizard.get_task_extra_parser(task_name)
                extra_args = [{act.option_strings[0]: act.type} for act in parser._actions]
                match task_name:
                    case '_iblrig_tasks_advancedChoiceWorld':
                        expect = 6
                    case '_iblrig_tasks_trainingPhaseChoiceWorld':
                        expect = 3
                    case '_iblrig_tasks_trainingChoiceWorld':
                        expect = 4
                    case '_iblrig_tasks_ephysChoiceWorld':
                        expect = 2
                    case '_iblrig_tasks_spontaneous':
                        expect = 0
                    case _:
                        print(task_name)
                        expect = len(extra_args)
                self.assertEqual(expect, len(extra_args))
