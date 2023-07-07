import numpy as np
from iblrig.test.base import TASK_KWARGS
from iblrig.test.tasks.test_biased_choice_world import TestInstantiationBiased
from iblrig_tasks._iblrig_tasks_neuroModulatorChoiceWorld.task import Session as NeuroModulatorChoiceWorldSession


class TestNeuroModulatorBiasedChoiceWorld(TestInstantiationBiased):
    def setUp(self) -> None:
        self.task = NeuroModulatorChoiceWorldSession(**TASK_KWARGS)

    def test_task(self):
        super(TestNeuroModulatorBiasedChoiceWorld, self).test_task()
        # we expect 10% of null feedback trials
        assert np.abs(.05 - np.mean(self.task.trials_table['omit_feedback'])) < .05
