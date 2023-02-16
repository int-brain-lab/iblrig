from pathlib import Path
import unittest

from iblrig.raw_data_loaders import load_task_jsonable


class TestLoadTaskData(unittest.TestCase):

    def test_load_task_jsonable(self):
        jsonable_file = Path(__file__).parent.joinpath('fixtures', 'task_data.jsonable')
        trials_table, bpod_data = load_task_jsonable(jsonable_file)
        assert trials_table.shape[0] == 2
        assert len(bpod_data) == 2
