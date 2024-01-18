import unittest
from pathlib import Path

import numpy as np

from iblrig.raw_data_loaders import load_task_jsonable


class TestLoadTaskData(unittest.TestCase):
    def test_load_task_jsonable(self):
        jsonable_file = Path(__file__).parent.joinpath('fixtures', 'task_data_short.jsonable')
        trials_table, bpod_data = load_task_jsonable(jsonable_file)
        assert trials_table.shape[0] == 2
        assert len(bpod_data) == 2

    def test_load_task_jsonable_partial(self):
        jsonable_file = Path(__file__).parent.joinpath('fixtures', 'task_data_short.jsonable')
        with open(jsonable_file) as fp:
            fp.readline()
            offset = fp.tell()
        trials_table, bpod_data = load_task_jsonable(jsonable_file, offset=offset)

        trials_table_full, bpod_data_full = load_task_jsonable(jsonable_file)
        for c in trials_table.columns:
            if not np.isnan(trials_table[c][0]):
                np.testing.assert_equal(trials_table_full[c].values[-1], trials_table[c][0])

        assert bpod_data_full[-1] == bpod_data[0]
