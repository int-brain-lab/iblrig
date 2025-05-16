import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib
import numpy as np

import iblrig.gui.online_plots as op
from iblrig.raw_data_loaders import load_task_jsonable

zip_jsonable = Path(__file__).parent.joinpath('fixtures', 'online_plots_biased_iblrigv7.zip')
matplotlib.use('Agg')  # avoid pyqt testing issues


class TestOnlinePlots(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()
        cls.task_dir = Path(cls.temp_dir.name).joinpath('raw_task_data_00')
        cls.task_dir.mkdir()
        with zipfile.ZipFile(zip_jsonable, 'r') as zip:
            task_file = Path(zip.extract('online_plots.jsonable', path=cls.task_dir))
            cls.task_file = Path(cls.task_dir).joinpath('_iblrig_taskData.raw.jsonable')
            task_file.rename(cls.task_file)

    def test_during_task(self):
        model = op.OnlinePlotsModel(self.task_dir)
        assert hasattr(model, 'jsonableWatcher')
        assert Path(model.jsonableWatcher.files()[0]) == self.task_file
        assert (n_trials := model._n_trials) > 0
        with open(self.task_file, 'r') as f:
            line = f.readline()
        with open(self.task_file, 'a') as f:
            f.writelines([line])
        model.readJsonable('')  # this would usually be called through model.jsonableWatcher
        assert model._n_trials == n_trials + 1

    def test_from_existing_file(self):
        model = op.OnlinePlotsModel(self.task_file)
        assert model._n_trials > 0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()
