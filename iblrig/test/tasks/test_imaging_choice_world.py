from iblrig.test.base import TASK_KWARGS
from iblrig.test.tasks.test_biased_choice_world import TestInstantationBiased
from iblrig_tasks._iblrig_tasks_ImagingChoiceWorld.task import Session as ImagingChoiceWorldSession


class TestNeuroModulatorBiasedChoiceWorld(TestInstantationBiased):
    def setUp(self) -> None:
        self.task = ImagingChoiceWorldSession(**TASK_KWARGS)

    def test_task(self):
        super(TestNeuroModulatorBiasedChoiceWorld, self).test_task()
