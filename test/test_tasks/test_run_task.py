import abc
import datetime
import json
import logging
from pathlib import Path
import unittest

from one.api import ONE
import iblrig
from iblrig.raw_data_loaders import load_task_jsonable
from iblrig_tasks._iblrig_tasks_biasedChoiceWorld.task import Session as BiasedChoiceWorldSession

log = logging.getLogger("iblrig")
path_fixtures = Path(__file__).parents[1].joinpath('fixtures')

class JsonSettingsMixin(abc.ABC):
    def read_and_assert_json_settings(self, json_file):
        with open(json_file, "r") as fp:
            settings = json.load(fp)
        # test a subset of keys useful for extraction
        self.assertIn('ALYX_USER', settings)
        self.assertEqual(settings['IBLRIG_VERSION'], iblrig.__version__)
        self.assertIn('PYBPOD_PROTOCOL', settings)
        self.assertIn('RIG_NAME', settings)
        self.assertIn('SESSION_END_TIME', settings)
        self.assertIn('SESSION_NUMBER', settings)
        dt = datetime.datetime.now() - datetime.datetime.fromisoformat(settings['SESSION_START_TIME'])
        self.assertLess(dt.seconds, 600)  # leaves some time for debugging
        self.assertEqual(settings['SUBJECT_WEIGHT'], None)
        return settings


class TestIntegrationBiasedTaskRun(unittest.TestCase, JsonSettingsMixin):

    def test_task(self):
        """
        Run mocked task for 3 trials
        Registers sessions on Alyx at startup, and post-hoc registers number of trials
        :return:
        """
        jsonable_file = path_fixtures.joinpath('task_data.jsonable')
        file_iblrig_settings = path_fixtures.joinpath('iblrig_settings_test.yaml')
        task = BiasedChoiceWorldSession(interactive=False, subject='KS005', iblrig_settings=file_iblrig_settings)
        task.mock(file_jsonable_fixture=jsonable_file)
        task.task_params.NTRIALS = 3
        task.run()
        file_settings = task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        settings = self.read_and_assert_json_settings(file_settings)
        # makes sure the session end time is labeled
        dt = datetime.datetime.now() - datetime.datetime.fromisoformat(settings['SESSION_END_TIME'])
        self.assertLess(dt.seconds, 600)  # leaves some time for debugging
        trials_table, bpod_data = load_task_jsonable(task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable'))
        assert trials_table.shape[0] == task.task_params.NTRIALS
        assert len(bpod_data) == task.task_params.NTRIALS


class TestFileOutput(unittest.TestCase, JsonSettingsMixin):
    def test_output_task_parameters_to_json_file(self):
        bcws = BiasedChoiceWorldSession(interactive=False, subject='unittest_subject')  # Create false session
        # Create json file and test
        json_file = bcws.save_task_parameters_to_json_file()
        self.read_and_assert_json_settings(json_file)
