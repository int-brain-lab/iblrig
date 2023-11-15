import numpy as np

from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession


class TestInstantiatePassiveChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.task = PassiveChoiceWorldSession(**TASK_KWARGS)
        self.task.mock()
        np.random.seed(12345)
