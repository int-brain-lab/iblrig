from iblrig.test.base import TASK_KWARGS
from iblrig_tasks._iblrig_tasks_ephysChoiceWorld.task import Session as EphysChoiceWorldSession

from iblrig.test.tasks.test_neuromodulator_biased_choice_world import TestInstantiationBiased


class TestInstantiationEphys(TestInstantiationBiased):
    def setUp(self) -> None:
        self.task = EphysChoiceWorldSession(**TASK_KWARGS)
