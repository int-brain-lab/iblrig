from iblrig.test.base import IntegrationFullRuns
from iblrig_tasks._iblrig_tasks_spontaneous.task import Session as SpontaneousSession


class Spontaneous(IntegrationFullRuns):
    def setUp(self) -> None:
        super().setUp()
        self.task = SpontaneousSession(one=self.one, duration_secs=2, **self.kwargs)

    def test_task_spontaneous(self):
        self.task.run()
        file_settings = self.task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        self.read_and_assert_json_settings(file_settings)
