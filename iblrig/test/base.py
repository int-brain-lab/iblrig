import datetime
import inspect
import json
import random
import string
from pathlib import Path
import unittest

from one.api import ONE

from ibllib.tests import TEST_DB  # noqa

import iblrig

PATH_FIXTURES = Path(__file__).parent.joinpath('fixtures')

TASK_KWARGS = {
    'file_iblrig_settings': 'iblrig_settings_template.yaml',
    'file_hardware_settings': 'hardware_settings_template.yaml',
    'subject': 'iblrig_test_subject',
    'interactive': False,
    'projects': ['ibl_neuropixel_brainwide_01', 'ibl_mainenlab'],
    'procedures': ['Behavior training/tasks', 'Imaging'],
}


class BaseTestCases():
    """
    We wrap the base class in a blank class to avoid it being called or discovered by unittest
    """

    class CommonTestTask(unittest.TestCase):
        task = None

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

    class CommonTestInstantiateTask(CommonTestTask):
        def test_json_settings(self):
            json_file = self.task.save_task_parameters_to_json_file()
            self.read_and_assert_json_settings(json_file)

        def test_graphviz(self) -> None:
            if hasattr(self.task, 'get_graphviz_task'):
                self.task.mock()
                pdf_out = Path(inspect.getfile(self.task.__class__)).parent.joinpath('state_machine_graph')
                self.task.get_graphviz_task(output_file=pdf_out, view=False)


class TestIntegrationFullRuns(BaseTestCases.CommonTestTask):
    """
    This provides a base class that creates a subject on the test database for testing
    the full registration / run / register results cycle
    """
    @classmethod
    def setUpClass(cls) -> None:
        """
        Instantiates ONE test, creates a random subject to be deleted once all of the operations
        have completed
        :return:
        """
        cls.one = ONE(**TEST_DB, mode='remote')
        cls.kwargs = TASK_KWARGS
        cls.kwargs['subject'] = 'iblrig_unit_test_' + ''.join(random.choices(string.ascii_letters, k=8))
        cls.one.alyx.rest('subjects', 'create', data=dict(nickname=cls.kwargs['subject'], lab='cortexlab'))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.one.alyx.rest('subjects', 'delete', id=cls.kwargs['subject'])
