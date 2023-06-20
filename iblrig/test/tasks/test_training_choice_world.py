from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from iblrig.test.base import TASK_KWARGS, BaseTestCases


class TestInstantiationTraining(BaseTestCases.CommonTestInstantiateTask):

    def setUp(self) -> None:
        self.task = TrainingChoiceWorldSession(**TASK_KWARGS)
