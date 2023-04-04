import unittest
import numpy as np
from pathlib import Path
import zipfile
import matplotlib

import iblrig.online_plots as op
from iblrig.raw_data_loaders import load_task_jsonable

zip_jsonable = Path(__file__).parent.joinpath('fixtures', 'online_plots_biased_iblrigv7.zip')
matplotlib.use('Agg')  # avoid pyqt testing issues


class TestOnlineStd(unittest.TestCase):

    def test_online_std(self):
        n = 41
        b = np.random.rand(n)
        a = b[:-1]
        mu, std = op.online_std(new_sample=b[-1], count=n, mean=np.mean(a), std=np.std(a))
        np.testing.assert_almost_equal(std, np.std(b))
        np.testing.assert_almost_equal(mu, np.mean(b))


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
