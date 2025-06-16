import numpy as np
import pandas as pd

from iblrig import choiceworld
from iblrig.test.base import BaseTestCases
from iblrig.test.tasks.test_biased_choice_world_family import get_fixtures
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from iblrig_tasks._iblrig_tasks_trainingPhaseChoiceWorld.task import Session as TrainingPhaseChoiceWorldSession


class TestTrainingPhaseChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self):
        self.get_task_kwargs()
        self.task = TrainingPhaseChoiceWorldSession(**self.task_kwargs)

    def test_task(self):
        """
        This test loops over training phases described in the mice training
        protocol and runs full sessions with each training phase parameter
        (cf. Appendix 2). It then checks for:

        -   the contrast set
        -   the presence or absence of debias trials
        -   the relative frequency of each contrast
        """
        trial_fixtures = get_fixtures()
        adaptive_reward = 1.9
        n_trials = 800
        for training_phase in np.arange(6):
            with self.subTest(training_phase=training_phase):
                np.random.seed(12354)
                task = TrainingPhaseChoiceWorldSession(
                    **self.task_kwargs, adaptive_reward=adaptive_reward, training_level=training_phase
                )
                assert task.training_phase == training_phase
                task.create_session()
                for i_trial in range(n_trials):
                    task.next_trial()
                    assert task.trial_num == i_trial
                    trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
                    task.trial_completed(trial_fixtures[trial_type])
                    if trial_type == 'correct':
                        self.assertTrue(task.trials_table['trial_correct'][task.trial_num])
                        self.assertEqual(task.trials_table['reward_amount'][task.trial_num], adaptive_reward)
                    else:
                        assert not task.trials_table['trial_correct'][task.trial_num]
                    assert not np.isnan(task.reward_time)
                trials_table = task.trials_table[: task.trial_num].copy()
                contrasts = (
                    trials_table.groupby(['contrast']).agg(count=pd.NamedAgg(column='contrast', aggfunc='count')).reset_index()
                )
                np.testing.assert_equal(trials_table['stim_probability_left'].to_numpy(), 0.5)
                np.testing.assert_equal(np.unique(trials_table['reward_amount'].values), np.array([0, adaptive_reward]))
                np.testing.assert_equal(trials_table['training_phase'].to_numpy(), training_phase)
                debias = True
                probas = 1
                match training_phase:
                    case 5:
                        contrast_set = np.array([0, 0.0625, 0.125, 0.25, 1.0])
                        probas = np.array([1, 2, 2, 2, 2])
                        debias = False
                    case 4:
                        contrast_set = np.array([0, 0.0625, 0.125, 0.25, 0.5, 1.0])
                        probas = np.array([1, 2, 2, 2, 2, 2])
                    case 3:
                        contrast_set = np.array([0.0625, 0.125, 0.25, 0.5, 1.0])
                    case 2:
                        contrast_set = np.array([0.125, 0.25, 0.5, 1.0])
                    case 1:
                        contrast_set = np.array([0.25, 0.5, 1.0])
                    case 0:
                        contrast_set = np.array([0.5, 1.0])

                np.testing.assert_equal(contrasts['contrast'].values, contrast_set)
                normalized_counts = np.abs(n_trials / contrast_set.size - contrasts['count'].values)
                normalized_counts = normalized_counts * probas / np.sum(probas)
                normalized_counts = normalized_counts / (n_trials / contrast_set.size)
                np.testing.assert_array_less(normalized_counts, 0.33)
                if debias:
                    for index, row in trials_table.iterrows():
                        # if the previous trial was incorrect, not a no-go and easy
                        assert row.debias_trial == (
                            (index > 0)
                            and (trials_table.loc[index - 1, 'trial_correct'] != 1)
                            and (trials_table.loc[index - 1, 'response_side'] != 0)
                            and (trials_table.loc[index - 1, 'contrast'] >= 0.5)
                        )
                        if row.debias_trial:
                            assert row.position in task.task_params['STIM_POSITIONS']
                            assert trials_table.loc[index - 1, 'contrast'] == row.contrast
                    assert trials_table.debias_trial.sum() > 0
                else:
                    assert trials_table.debias_trial.sum() == 0


class TestInstantiationTraining(BaseTestCases.CommonTestInstantiateTask):
    @classmethod
    def setUpClass(cls):
        cls.trial_fixtures = get_fixtures()
        cls.adaptive_reward = 1.9

    def setUp(self):
        self.get_task_kwargs()
        self.task = TrainingChoiceWorldSession(**self.task_kwargs, adaptive_reward=self.adaptive_reward)
        self.task.create_session()

    def test_task(self):
        for i_trial in range(1300):
            original_phase = self.task.training_phase
            self.task.next_trial()
            assert self.task.trial_num == i_trial
            performance = choiceworld.compute_performance(self.task.trials_table)
            did_progress = self.task.training_phase > original_phase
            trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
            self.task.trial_completed(self.trial_fixtures[trial_type])

            # assert outcome and reward
            if trial_type == 'correct':
                self.assertTrue(self.task.trials_table['trial_correct'][self.task.trial_num])
                self.assertEqual(self.task.trials_table['reward_amount'][self.task.trial_num], self.adaptive_reward)
            else:
                self.assertFalse(self.task.trials_table['trial_correct'][self.task.trial_num])
            assert not np.isnan(self.task.reward_time)
            if i_trial == 0:
                continue

            # assert correct progression through training phases
            should_progress = False
            if original_phase == 0:
                # The proportion of correct responses over the previous 50 trials is recorded.
                # To progress, the mouse must perform at or above 80% correct for each contrast on both sides.
                last_50_perf = performance[abs(performance.index) >= 0.5]['last_50_perf']
                should_progress = all(last_50_perf > 0.8) and (last_50_perf.size == 4)
            elif original_phase == 1:
                # To progress the mouse must perform at or above 80% on each of the 25% contrast last 50 trials.
                last_50_perf = performance[abs(performance.index) == 0.25]['last_50_perf'] > 0.8
                should_progress = all(last_50_perf) and (last_50_perf.size == 2)
            elif 5 > original_phase >= 2:
                # To progress the mouse must perform 200 trials, regardless of performance.
                if (self.task.trials_table.loc[: i_trial - 1].training_phase == original_phase).sum() >= 200:
                    should_progress = True
            assert did_progress == should_progress
        self.assertEqual(self.task.trials_table.at[i_trial, 'training_phase'], 5)

        # assert contrast levels
        for phase in range(6):
            actual_contrasts = np.sort(self.task.trials_table[self.task.trials_table.training_phase == phase].contrast.unique())
            match phase:
                case 0:  # Only 50% and 100% contrasts are presented.
                    expected_contrasts = [0.5, 1.0]
                case 1:  # The 25% contrast is added to the set
                    expected_contrasts = [0.25, 0.5, 1.0]
                case 2:  # The 12.5% contrast is added to the set.
                    expected_contrasts = [0.125, 0.25, 0.5, 1.0]
                case 3:  # The 6.25% contrast is added to the set.
                    expected_contrasts = [0.0625, 0.125, 0.25, 0.5, 1.0]
                case 4:  # The 0% contrast is added to the set.
                    expected_contrasts = [0, 0.0625, 0.125, 0.25, 0.5, 1.0]
                case _:  # The 50% contrast is removed from the set.
                    expected_contrasts = [0, 0.0625, 0.125, 0.25, 1.0]
            np.testing.assert_equal(actual_contrasts, expected_contrasts)

    def test_acquisition_description(self):
        actual_description = self.task.experiment_description
        expected_description = {
            'sync': {
                'bpod': {
                    'collection': 'raw_task_data_00',
                    'extension': '.jsonable',
                    'acquisition_software': 'pybpod',
                },
            },
            'devices': {
                'cameras': {
                    'left': {
                        'collection': 'raw_video_data',
                        'sync_label': 'audio',
                    },
                },
                'microphone': {
                    'microphone': {
                        'collection': 'raw_task_data_00',
                        'sync_label': 'audio',
                    },
                },
            },
            'tasks': [{'_iblrig_tasks_trainingChoiceWorld': {'collection': 'raw_task_data_00'}}],
        }
        self.assertDictContainsSubset(expected_description, actual_description)
