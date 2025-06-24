import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from iblrig import raw_data_loaders
from iblrig.test.base import PATH_FIXTURES


class TestRawDataLoaders(unittest.TestCase):
    jsonable = Path(PATH_FIXTURES).joinpath('task_data_short.jsonable')

    def test_load_task_jsonable(self):
        trials_table, bpod_data = raw_data_loaders.load_task_jsonable(self.jsonable)
        assert len(trials_table) == len(bpod_data)
        assert isinstance(trials_table, pd.DataFrame)
        assert isinstance(bpod_data, list)
        assert isinstance(bpod_data[0], dict)
        self.assertListEqual(
            list(bpod_data[0].keys()),
            ['Bpod start timestamp', 'Trial start timestamp', 'Trial end timestamp', 'States timestamps', 'Events timestamps'],
        )
        with self.jsonable.open('r') as f:
            trial0 = json.loads(f.readline())
            bpod_data0 = trial0.pop('behavior_data')
            pos = f.tell()
        trials_table2, bpod_data2 = raw_data_loaders.load_task_jsonable(self.jsonable, pos)
        assert trials_table.iloc[0].equals(pd.Series(trial0))
        assert trials_table.iloc[1:].reset_index(drop=True).equals(trials_table2)
        self.assertDictEqual(bpod_data[0], bpod_data0)
        self.assertListEqual(bpod_data[1:], bpod_data2)

    def test_bpod_trial_data_to_dataframe(self):
        _, bpod_data = raw_data_loaders.load_task_jsonable(self.jsonable)
        data = raw_data_loaders.bpod_trial_data_to_dataframe(bpod_data[0], 0)
        assert isinstance(data, pd.DataFrame)
        self.assertListEqual(data.columns.to_list(), ['Type', 'State', 'Trial', 'Event', 'Channel', 'Value'])
        assert np.all(np.diff(data.index).astype(float) >= 0.0)

    def test_bpod_session_data_to_dataframe(self):
        _, bpod_data = raw_data_loaders.load_task_jsonable(self.jsonable)
        data = raw_data_loaders.bpod_session_data_to_dataframe(bpod_data)
        assert isinstance(data, pd.DataFrame)
        self.assertListEqual(data.columns.to_list(), ['Type', 'State', 'Trial', 'Event', 'Channel', 'Value'])
        assert np.all(np.diff(data.index).astype(float) >= 0.0)
        assert data.Trial.iloc[0] == 0
        assert data.Trial.iloc[-1] == len(bpod_data) - 1

    def test_bpod_trial_data_to_dataframes(self):
        _, bpod_data = raw_data_loaders.load_task_jsonable(self.jsonable)
        data = raw_data_loaders.bpod_trial_data_to_dataframes(bpod_data)
        assert isinstance(data, list)
        assert isinstance(data[0], pd.DataFrame)
        assert len(data) == len(bpod_data)
        self.assertListEqual(data[0].columns.to_list(), ['Type', 'State', 'Trial', 'Event', 'Channel', 'Value'])
