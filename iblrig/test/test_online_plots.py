import os
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import iblrig.gui.online_plots as op

zip_jsonable = Path(__file__).parent.joinpath('fixtures', 'online_plots_biased_iblrigv7.zip')


@pytest.mark.skipif(
    os.getenv('GITHUB_ACTIONS') == 'true' and os.name == 'posix' and os.uname().sysname == 'Linux',
    reason='Skipping test on GitHub Actions Ubuntu runners',
)
class TestOnlinePlots:
    @pytest.fixture
    def task_file(self):
        temp_dir = TemporaryDirectory()
        task_dir = Path(temp_dir.name).joinpath('raw_task_data_00')
        task_dir.mkdir()
        with zipfile.ZipFile(zip_jsonable, 'r') as z:
            task_file = Path(z.extract('online_plots.jsonable', path=task_dir))
            task_file_renamed = Path(task_dir).joinpath('_iblrig_taskData.raw.jsonable')
            task_file.rename(task_file_renamed)

        yield task_file_renamed

        temp_dir.cleanup()

    def test_during_task(self, task_file, qtbot):
        view = op.OnlinePlotsView(task_file.parent)
        model = view.model
        assert hasattr(model, 'jsonableWatcher')
        assert Path(model.jsonableWatcher.files()[0]) == task_file
        assert (n_trials := model._n_trials) > 0
        with open(task_file) as f:
            line = f.readline()
        with qtbot.waitSignal(model.jsonableWatcher.fileChanged, timeout=5), open(task_file, 'a') as f:
            f.writelines([line])
        assert model._n_trials == n_trials + 1
        model.jsonableWatcher.removePath(str(task_file))

    def test_from_existing_file(self, task_file, qtbot):
        view = op.OnlinePlotsView(task_file)
        assert view.model._n_trials > 0
