import unittest
import zipfile
from pathlib import Path

import matplotlib
import numpy as np

import iblrig.online_plots as op
from iblrig.raw_data_loaders import load_task_jsonable

zip_jsonable = Path(__file__).parent.joinpath('fixtures', 'online_plots_biased_iblrigv7.zip')
matplotlib.use('Agg')  # avoid pyqt testing issues


class TestOnlinePlots(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with zipfile.ZipFile(zip_jsonable, 'r') as zip:
            cls.task_file = Path(zip.extract('online_plots.jsonable', path=zip_jsonable.parent))

    def test_during_task(self):
        myop = op.OnlinePlots()
        trials_table, bpod_data = load_task_jsonable(self.task_file)
        for i in np.arange(trials_table.shape[0]):
            myop.update_trial(trials_table.iloc[i], bpod_data[i])

    def test_from_existing_file(self):
        op.OnlinePlots(task_file=self.task_file)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.task_file.unlink()
