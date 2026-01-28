from unittest.mock import patch

from iblrig.test.base import IntegrationFullRuns
from iblrig_tasks._iblrig_tasks_spontaneous.task import Session as SpontaneousSession
from iblrig_tasks._iblrig_tasks_spontaneousBpod.task import Session as SpontaneousBpodSession


class Spontaneous(IntegrationFullRuns):
    def setUp(self) -> None:
        super().setUp()
        self.task = SpontaneousSession(one=self.one, duration_secs=2, **self.task_kwargs)

    def test_task_spontaneous(self):
        self.task.run()
        file_settings = self.task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        self.read_and_assert_json_settings(file_settings)
        assert self.task.paths.SESSION_FOLDER.joinpath('transfer_me.flag').exists(), 'transfer_me.flag not found'


class SpontaneousBpod(IntegrationFullRuns):
    def setUp(self) -> None:
        super().setUp()
        self.task = SpontaneousBpodSession(one=self.one, duration_secs=2, **self.task_kwargs)

    @patch('iblrig.hardware.Bpod', autospec=True)
    @patch('iblrig.base_tasks.BpodMixin.send_spacers')
    def test_task_spontaneous_bpod(self, mock_send_spacers, *_):
        self.task.hardware_settings['device_bpod']['COM_BPOD'] = 'FakePort'
        self.task.run()
        mock_send_spacers.assert_called_once()
        file_settings = self.task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        self.read_and_assert_json_settings(file_settings)
