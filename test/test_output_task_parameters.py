import os.path

import json
import unittest

from iblrig_tasks._iblrig_tasks_biasedChoiceWorld.task import Session as BiasedChoiceWorldSession


class TestOutputTaskParameters(unittest.TestCase):
    def test_parameters(self):
        # Create false session
        bcws = BiasedChoiceWorldSession(interactive=False, subject='unittest_subject')

        # Grab parameters from task_params object
        output_dict = dict(bcws.task_params)

        # Grab hardware settings from object
        output_dict.update(dict(bcws.hardware_settings))

        # Output dict to json file
        json_file = bcws.paths.SESSION_FOLDER / "output_task_parameters.json"
        with open(json_file, "w") as outfile:
            json.dump(output_dict, outfile, indent=4, sort_keys=True, default=str)  # converts datetime objects to string

        # Ensure file exists and is in json format
        assert os.path.isfile(json_file)
