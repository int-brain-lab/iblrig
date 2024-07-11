import numpy as np

from iblrig.test.base import BaseTestCases
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession


class TestInstantiatePassiveChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        session_id = 7
        self.get_task_kwargs()
        self.task = PassiveChoiceWorldSession(**self.task_kwargs, session_template_id=session_id)
        self.task.mock()
        assert np.unique(self.task.trials_table['session_id']) == [session_id]
        np.random.seed(12345)
