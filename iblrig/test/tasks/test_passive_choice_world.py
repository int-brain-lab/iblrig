import numpy as np

from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession


class TestInstantiatePassiveChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        session_id = 7
        self.task = PassiveChoiceWorldSession(**TASK_KWARGS, session_template_id=session_id)
        self.task.mock()
        assert np.unique(self.task.trials_table["session_id"]) == [session_id]
        np.random.seed(12345)
