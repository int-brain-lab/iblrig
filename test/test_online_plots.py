import unittest
import numpy as np
import iblrig.online_plots as op
from iblrig.raw_data_loaders import load_task_jsonable
# task_file = "/Users/olivier/Library/CloudStorage/GoogleDrive-olivier.winter@internationalbrainlab.org/My Drive/2023/02_Neuromodulators/ZFM-04022/2023-02-15/001/raw_behavior_data/_iblrig_taskData.raw.jsonable"
task_file = "/datadisk/FlatIron/hausserlab/Subjects/PL037/2023-02-24/001/raw_behavior_data/_iblrig_taskData.raw.jsonable"


class TestOnlinePlots(unittest.TestCase):

    def test_online_std(self):
        n = 41
        b = np.random.rand(n)
        a = b[:-1]
        mu, std = op.online_std(new_sample=b[-1], count=n, mean=np.mean(a), std=np.std(a))
        np.testing.assert_almost_equal(std, np.std(b))
        np.testing.assert_almost_equal(mu, np.mean(b))

    def test_during_task(self):
        self = op.OnlinePlots()
        trials_table, bpod_data = load_task_jsonable(task_file)
        for i in np.arange(trials_table.shape[0]):
            self.update_trial(trials_table.iloc[i], bpod_data[i])

    def test_from_existing_file(self):
        op.OnlinePlots(task_file=task_file)
