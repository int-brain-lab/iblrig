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
        This test loops over training phases described in the mice training protocol and runs full
        sessions with each training phase parameter
        https://docs.google.com/document/d/1RA6wgbWfxD2kGlpNxt0n3HVcW4TEIx8e-YO7k_W1pHs/edit
        It then checks for:
        -   the contrast set
        -   the presence or absence of debias trials
        -   the relative frequency of each contrast
        :return:
        """
        trial_fixtures = get_fixtures()
        adaptive_reward = 1.9
        nt = 800
        for training_phase in np.arange(6):
            with self.subTest(training_phase=training_phase):
                np.random.seed(12354)
                task = TrainingPhaseChoiceWorldSession(
                    **self.task_kwargs, adaptive_reward=adaptive_reward, training_level=training_phase
                )
                assert task.training_phase == training_phase
                task.create_session()
                for _i in np.arange(nt):
                    task.next_trial()
                    # pc = task.psychometric_curve()
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
                normalized_counts = np.abs(nt / contrast_set.size - contrasts['count'].values)
                normalized_counts = normalized_counts * probas / np.sum(probas)
                normalized_counts = normalized_counts / (nt / contrast_set.size)
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
    def setUp(self):
        self.get_task_kwargs()
        self.task = TrainingChoiceWorldSession(**self.task_kwargs)

    def test_task(self):
        trial_fixtures = get_fixtures()
        adaptive_reward = 1.9
        n_trials = 800

        task = TrainingChoiceWorldSession(**self.task_kwargs, adaptive_reward=adaptive_reward)
        task.create_session()
        np.random.seed(12354)
        for i_trial in range(n_trials):
            original_phase = task.training_phase
            task.next_trial()
            performance = choiceworld.compute_performance(task.trials_table)
            did_progress = task.training_phase > original_phase
            assert task.trial_num == i_trial
            # pc = task.psychometric_curve()
            trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
            task.trial_completed(trial_fixtures[trial_type])
            if trial_type == 'correct':
                self.assertTrue(task.trials_table['trial_correct'][task.trial_num])
                self.assertEqual(task.trials_table['reward_amount'][task.trial_num], adaptive_reward)
            else:
                assert not task.trials_table['trial_correct'][task.trial_num]
            if i_trial == 245:
                task.show_trial_log()
            assert not np.isnan(task.reward_time)

            # assert correct progression through training phases
            should_graduate = False
            if i_trial == 0:
                continue
            if original_phase == 0:
                assert task.trials_table.iloc[i_trial - 1].contrast in [0.5, 1.0]
                passing = performance[np.abs(performance.index) >= 0.5]['last_50_perf'] > 0.8
                should_graduate = np.all(passing) and (passing.size == 4)
            elif original_phase == 1:
                assert task.trials_table.iloc[i_trial - 1].contrast in [0.25, 0.5, 1.0]
                passing = performance[np.abs(performance.index) == 0.25]['last_50_perf'] > 0.8
                should_graduate = np.all(passing) and (passing.size == 2)
            elif original_phase >= 2:
                if (task.trials_table.loc[: i_trial - 1].training_phase == original_phase).sum() >= 200:
                    should_graduate = True
            assert did_progress == should_graduate
        # we should have progressed beyond phase 3
        np.testing.assert_equal(task.trials_table['training_phase'].value_counts().sort_index().values, [181, 475, 144])

    def test_acquisition_description(self):
        """Test that the acquisition description of the task matches the expected structure and values."""
        actual_dict = self.task.experiment_description
        expected_dict = {
            'sync': {'bpod': {'collection': 'raw_task_data_00', 'extension': '.jsonable', 'acquisition_software': 'pybpod'}},
            'devices': {
                'cameras': {'left': {'collection': 'raw_video_data', 'sync_label': 'audio'}},
                'microphone': {'microphone': {'collection': 'raw_task_data_00', 'sync_label': 'audio'}},
            },
            'tasks': [{'_iblrig_tasks_trainingChoiceWorld': {'collection': 'raw_task_data_00'}}],
        }
        for key, expected_value in expected_dict.items():
            assert key in actual_dict, f'Acquisition description does not match expected structure. No such key: `{key}`.'
            assert actual_dict[key] == expected_value, (
                f'Acquisition description does not match expected structure. Failed on key `{key}`.'
            )
