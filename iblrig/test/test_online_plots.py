import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import iblrig.gui.online_plots as op

zip_jsonable = Path(__file__).parent.joinpath('fixtures', 'online_plots_biased_iblrigv7.zip')


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

    def test_colors(self, task_file, qtbot):
        view = op.OnlinePlotsView(task_file.parent)
        model = view.model
        model._trial_data['response_time'] = 1
        model._seconds_elapsed = 0
        model._trials_elapsed = 0
        model.compute_end_session_criteria()
        assert model.titleColor == op.Colors.TRANSPARENT

        # if the mouse has been training for more than 90 minutes subject training too long -> RED
        with qtbot.assertNotEmitted(model.titleColorChanged):
            model._seconds_elapsed = 90 * 60
            model.compute_end_session_criteria()
        with qtbot.waitSignal(model.titleColorChanged, timeout=5):
            model._seconds_elapsed += 1
            model.compute_end_session_criteria()
            assert model.titleColor == op.Colors.RED

        # the mouse fails to do more than 400 trials in the first 45 mins -> GREEN
        model._seconds_elapsed = 45 * 60
        model.compute_end_session_criteria()
        with qtbot.assertNotEmitted(model.titleColorChanged):
            model._n_trials_engaged = 401
            model.compute_end_session_criteria()
        with qtbot.waitSignal(model.titleColorChanged, timeout=5):
            model._n_trials_engaged -= 1
            model.compute_end_session_criteria()
            assert model.titleColor == op.Colors.GREEN

        # reaction time over last 20 trials is more than 5 times greater than the overall reaction time -> YELLOW
        model._n_trials_engaged = 401
        model.compute_end_session_criteria()
        with qtbot.assertNotEmitted(model.titleColorChanged):
            model._trial_data.loc[model._trial_data.index[-20:], 'response_time'] = 5
            model.compute_end_session_criteria()
            assert model.titleColor == op.Colors.TRANSPARENT
        with qtbot.waitSignal(model.titleColorChanged, timeout=5):
            model._trial_data.loc[model._trial_data.index[-20:], 'response_time'] = 6
            model.compute_end_session_criteria()
            assert model.titleColor == op.Colors.YELLOW

        model.jsonableWatcher.removePath(str(task_file))
