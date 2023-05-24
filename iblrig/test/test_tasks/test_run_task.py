import abc
import datetime
import json
import logging
import random
import string
import unittest

from one.api import ONE
import iblrig.test
from iblrig.raw_data_loaders import load_task_jsonable
from iblrig_tasks._iblrig_tasks_biasedChoiceWorld.task import Session as BiasedChoiceWorldSession
from iblrig_tasks._iblrig_tasks_spontaneous.task import Session as SpontaneousSession

log = logging.getLogger("iblrig")


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
        self.assertIn('SUBJECT_WEIGHT', settings)
        return settings


class TestIntegrationBiasedTaskRun(unittest.TestCase, JsonSettingsMixin):

    def setUp(self) -> None:
        """
        Instantiates ONE test, creates a random subject to be deleted once all of the operations
        have completed
        :return:
        """
        self.one = ONE(**iblrig.test.TEST_DB, mode='remote')
        self.kwargs = iblrig.test.TASK_KWARGS
        self.kwargs['subject'] = 'iblrig_unit_test_' + ''.join(random.choices(string.ascii_letters, k=8))
        self.one.alyx.rest('subjects', 'create', data=dict(nickname=self.kwargs['subject'], lab='cortexlab'))

    def test_task_spontaneous(self):
        task = SpontaneousSession(one=self.one, duration_secs=2, **self.kwargs)
        task.run()
        file_settings = task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        self.read_and_assert_json_settings(file_settings)

    def test_task_biased(self):
        """
        Run mocked task for 3 trials
        Registers sessions on Alyx at startup, and post-hoc registers number of trials
        :return:
        """
        task = BiasedChoiceWorldSession(one=self.one, **self.kwargs)
        task.mock(file_jsonable_fixture=iblrig.test.path_fixtures.joinpath('task_data_short.jsonable'),)
        task.task_params.NTRIALS = 3
        task.session_info['SUBJECT_WEIGHT'] = 24.2  # manually add a weighing
        task.run()
        file_settings = task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')

        settings = self.read_and_assert_json_settings(file_settings)
        # makes sure the session end time is labeled
        dt = datetime.datetime.now() - datetime.datetime.fromisoformat(settings['SESSION_END_TIME'])
        self.assertLess(dt.seconds, 600)  # leaves some time for debugging
        trials_table, bpod_data = load_task_jsonable(task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable'))
        assert trials_table.shape[0] == task.task_params.NTRIALS
        assert len(bpod_data) == task.task_params.NTRIALS
        # test that Alyx registration went well, we should find the session
        ses = self.one.alyx.rest('sessions', 'list', subject=self.kwargs['subject'],
                                 date=task.session_info['SESSION_START_TIME'][:10], number=task.session_info['SESSION_NUMBER'])
        full_session = self.one.alyx.rest('sessions', 'read', id=ses[0]['id'])
        # and the water administered
        assert full_session['wateradmin_session_related'][0]['water_administered'] == task.session_info['TOTAL_WATER_DELIVERED']
        # and the related weighing
        wei = self.one.alyx.rest('weighings', 'list', nickname=self.kwargs['subject'],
                                 date=task.session_info['SESSION_START_TIME'][:10])
        assert wei[0]['weight'] == task.session_info['SUBJECT_WEIGHT']

    def tearDown(self) -> None:
        self.one.alyx.rest('subjects', 'delete', id=self.kwargs['subject'])


class TestFileOutput(unittest.TestCase, JsonSettingsMixin):
    def test_output_task_parameters_to_json_file(self):
        bcws = BiasedChoiceWorldSession(**iblrig.test.TASK_KWARGS)  # Create false session
        # Create json file and test
        json_file = bcws.save_task_parameters_to_json_file()
        self.read_and_assert_json_settings(json_file)
