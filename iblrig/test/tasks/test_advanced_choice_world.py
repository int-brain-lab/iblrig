import numpy as np

from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig.test.tasks.test_biased_choice_world_family import get_fixtures
from iblrig_tasks._iblrig_tasks_advancedChoiceWorld.task import Session as AdvancedChoiceWorldSession


class TestInstantiationAdvanced(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.task = AdvancedChoiceWorldSession(
            probability_set=[1, 1, 1, 1, 1, 1],
            contrast_set=[-1, -.5, 0, 0, .5, 1],
            reward_set_ul=[1, 1.5, 2, 2, 2.5, 2.6],
            position_set=[-35, -35, -35, 35, 35, 35],
            **TASK_KWARGS
        )

    def test_task(self):
        task = self.task
        task.create_session()
        trial_fixtures = get_fixtures()
        nt = 800
        for i in np.arange(nt):
            task.next_trial()
            # pc = task.psychometric_curve()
            trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
            task.trial_completed(trial_fixtures[trial_type])
            if trial_type == 'correct':
                assert task.trials_table['trial_correct'][task.trial_num]
            else:
                assert not task.trials_table['trial_correct'][task.trial_num]

            if i == 245:
                task.show_trial_log()
            assert not np.isnan(task.reward_time)
