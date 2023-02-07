import unittest
from pathlib import Path, PosixPath

from iblrig.iotasks import output_task_parameters_to_json_file
from iblrig_tasks._iblrig_tasks_biasedChoiceWorld.task import Session as BiasedChoiceWorldSession


class TestIOTasks(unittest.TestCase):
    def test_output_task_parameters_to_json_file(self):
        bcws = BiasedChoiceWorldSession(interactive=False, subject='unittest_subject')  # Create false session

        # Create json file and test
        json_file = output_task_parameters_to_json_file(bcws)
        self.assertTrue(type(json_file) is PosixPath)
        self.assertTrue(Path.exists(json_file))
