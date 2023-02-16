import unittest
from pathlib import Path
import logging

from iblrig_tasks._iblrig_tasks_biasedChoiceWorld.task import Session as BiasedChoiceWorldSession

log = logging.getLogger("iblrig")


class TestTaskRun(unittest.TestCase):

    def test_task(self):
        """
        Run mocked task for 3 trials
        :return:
        """
        jsonable_file = Path(__file__).parents[1].joinpath('fixtures', 'task_data.jsonable')
        self = BiasedChoiceWorldSession(interactive=False, subject='subject_test_iblrigv8')
        self.mock(file_jsonable_fixture=jsonable_file)
        self.task_params.NTRIALS = 3
        self.run()
        assert self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json').exists()
        from iblrig.raw_data_loaders import load_task_jsonable
        trials_table, bpod_data = load_task_jsonable(self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable'))
        assert trials_table.shape[0] == self.task_params.NTRIALS
        assert len(bpod_data) == self.task_params.NTRIALS
