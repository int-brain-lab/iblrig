import time

import numpy as np

from iblrig_tasks._iblrig_tasks_habituationChoiceWorld.task import Session as HabituationChoiceWorldSession
from iblrig_tests.base import TASK_KWARGS, BaseTestCases


class TestInstantiateHabituationChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.task = HabituationChoiceWorldSession(**TASK_KWARGS)
        np.random.seed(12345)

    def test_task(self):
        task = self.task
        nt = 500
        t = np.zeros(nt)
        for i in np.arange(nt):
            t[i] = time.time()
            task.next_trial()
            if i == 245:
                task.show_trial_log()
