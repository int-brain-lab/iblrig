import numpy as np
import pandas as pd

from iblrig.test.base import BaseTestCases
from iblrig.test.tasks.test_biased_choice_world_family import get_fixtures
from iblrig_tasks._iblrig_tasks_advancedChoiceWorld.task import Session as AdvancedChoiceWorldSession


class TestDefaultParameters(BaseTestCases.CommonTestTask):
    def test_params_yaml(self):
        # just make sure the parameter file is
        self.get_task_kwargs(tmpdir=False)
        task = AdvancedChoiceWorldSession(**self.task_kwargs)
        self.assertEqual(12, task.df_contingencies.shape[0])
        self.assertEqual(task.task_params['PROBABILITY_LEFT'], 0.5)


class TestInstantiationAdvanced(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.get_task_kwargs()
        self.task = AdvancedChoiceWorldSession(
            probability_set=[2.0, 2.0, 2.0, 1.0, 1.0, 1.0],
            contrast_set=[1.0, 0.5, 0.0, 0.0, 0.5, 1.0],
            reward_set_ul=[1.0, 1.5, 2.0, 2.0, 2.5, 2.6],
            position_set=[-35, -35, -35, 35, 35, 35],
            **self.task_kwargs,
        )

    def test_task(self):
        task = self.task
        task.create_session()
        # given the table probabilities above, the left stimulus is twice as likely to be right
        self.assertTrue(task.task_params['PROBABILITY_LEFT'] == 2 / 3)
        # run a fake task for 800 trials
        trial_fixtures = get_fixtures()
        nt = 800
        np.random.seed(65432)

        for i in np.arange(nt):
            task.next_trial()
            # pc = task.psychometric_curve()
            trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
            task.trial_completed(bpod_data=trial_fixtures[trial_type])
            if trial_type == 'correct':
                assert task.trials_table['trial_correct'][task.trial_num]
            else:
                assert not task.trials_table['trial_correct'][task.trial_num]
            if i == 245:
                task.show_trial_log()
            assert not np.isnan(task.reward_time)

        # check the contrasts and positions by aggregating the trials table
        df_contrasts = (
            task.trials_table.iloc[:nt, :]
            .groupby(['contrast', 'position'])
            .agg(
                count=pd.NamedAgg(column='reward_amount', aggfunc='count'),
                n_unique_rewards=pd.NamedAgg(column='reward_amount', aggfunc='nunique'),
                max_reward=pd.NamedAgg(column='reward_amount', aggfunc='max'),
                min_reward=pd.NamedAgg(column='reward_amount', aggfunc='min'),
            )
            .reset_index()
        )
        # the error trials have 0 reward while the correct trials have their assigned reward amount
        np.testing.assert_array_equal(df_contrasts['n_unique_rewards'], 2)
        np.testing.assert_array_equal(df_contrasts['min_reward'], 0)
        np.testing.assert_array_equal(df_contrasts['max_reward'], [2, 2, 1.5, 2.5, 1, 2.6])

        n_left = np.sum(df_contrasts['count'][df_contrasts['position'] < 0])
        n_right = np.sum(df_contrasts['count'][df_contrasts['position'] > 0])
        # the left stimulus is twice as likely to be shown
        self.assertTrue(n_left > (n_right * 1.5))
