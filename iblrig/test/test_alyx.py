"""Test iblrig.alyx module."""
import unittest
import tempfile
import random
import string
from pathlib import Path
import datetime
from copy import deepcopy

from one.tests import TEST_DB_1
from one.api import ONE

from iblrig import __version__
from iblrig.test.base import TASK_KWARGS
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession


class TestRegisterSession(unittest.TestCase):
    """Test iblrig.alyx.register_session function."""

    def setUp(self):
        # Create a temporary directory for task to write settings files to
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = Path(tmp.name)

        # Create a random new subject
        self.one = ONE(**TEST_DB_1, cache_rest=None)
        self.subject = ''.join(random.choices(string.ascii_letters, k=10))
        self.lab = 'mainenlab'
        self.one.alyx.rest('subjects', 'create', data={'lab': self.lab, 'nickname': self.subject})
        self.addCleanup(self.one.alyx.rest, 'subjects', 'delete', id=self.subject)

        # Task settings
        iblrig_settings = {'ALYX_LAB': self.lab, 'iblrig_local_subjects_path': self.tmpdir, 'iblrig_local_data_path': self.tmpdir}
        hardware_settings = {'RIG_NAME': self.one.alyx.rest('locations', 'list', lab=self.lab)[0]['name']}
        self.task_settings = {**TASK_KWARGS, 'subject': self.subject,
                              'iblrig_settings': iblrig_settings, 'hardware_settings': hardware_settings}

    def test_register_session(self):
        task = TrainingChoiceWorldSession(**self.task_settings, one=self.one)
        self.addCleanup(task._remove_file_loggers)
        task.create_session()  # calls register_to_alyx

        ses, = self.one.alyx.rest('sessions', 'list', subject=self.subject)
        self.assertEqual(self.lab, ses['lab'])
        self.assertEqual(task.session_info['SESSION_START_TIME'], ses['start_time'])
        # self.assertEqual(task.session_info['SESSION_END_TIME'], ses['end_time'])
        self.assertCountEqual(task.session_info['PROJECTS'], ses['projects'])
        self.assertEqual(task.protocol_name + __version__, ses['task_protocol'])

        # Test with chained protocol
        task_settings = deepcopy(self.task_settings)
        task_settings['hardware_settings']['MAIN_SYNC'] = False  # Must be false to append
        task_settings['procedures'][0] = 'Ephys recording with acute probe(s)'
        chained = TrainingChoiceWorldSession(**task_settings, one=self.one, append=True)
        # Add n trials, etc. This simulates the call to register_to_alyx in the run method
        chained.session_info.SESSION_END_TIME = (datetime.datetime.now() + datetime.timedelta(hours=60)).isoformat()
        chained.session_info.POOP_COUNT = 83
        chained.session_info['NTRIALS'], chained.session_info['NTRIALS_CORRECT'] = 100, 65
        chained.session_info['TOTAL_WATER_DELIVERED'] = 535
        # Create session saves both settings and description files
        chained.create_session()

        ses = self.one.alyx.get(ses['url'])  # fetch full session from alyx
        self.assertEqual(task_settings['hardware_settings']['RIG_NAME'], ses['location'])
        self.assertEqual(task.session_info['SESSION_START_TIME'], ses['start_time'])
        self.assertEqual(chained.session_info['SESSION_END_TIME'], ses['end_time'])
        expected_procedures = {*task.session_info['PROCEDURES'], *chained.session_info['PROCEDURES']}
        self.assertCountEqual(expected_procedures, ses['procedures'])
        self.assertEqual(chained.session_info.POOP_COUNT, ses['json']['POOP_COUNT'])
        expected_protocol = task.protocol_name + __version__ + '/' + chained.protocol_name + __version__
        self.assertEqual(expected_protocol, ses['task_protocol'])
        self.assertEqual(1, len(ses['wateradmin_session_related']))
        expected = chained.session_info['TOTAL_WATER_DELIVERED'] / 1e3
        self.assertEqual(expected, ses['wateradmin_session_related'][0]['water_administered'])


if __name__ == '__main__':
    unittest.main()
