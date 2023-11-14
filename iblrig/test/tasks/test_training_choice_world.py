import numpy as np
import pandas as pd

from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig.test.tasks.test_biased_choice_world_family import get_fixtures
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from iblrig_tasks._iblrig_tasks_trainingPhaseChoiceWorld.task import Session as TrainingPhaseChoiceWorldSession


class TestTrainingPhaseChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.task = TrainingChoiceWorldSession(**TASK_KWARGS)

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
        ADAPTIVE_REWARD = 1.9
        nt = 800
        for training_phase in np.arange(6):
            with self.subTest(training_phase=training_phase):
                np.random.seed(12354)
                task = TrainingPhaseChoiceWorldSession(
                    **TASK_KWARGS, adaptive_reward=ADAPTIVE_REWARD, training_level=training_phase
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
                        self.assertEqual(task.trials_table['reward_amount'][task.trial_num], ADAPTIVE_REWARD)
                    else:
                        assert not task.trials_table['trial_correct'][task.trial_num]
                    assert not np.isnan(task.reward_time)
                trials_table = task.trials_table[: task.trial_num].copy()
                contrasts = (
                    trials_table.groupby(['contrast'])
                    .agg(
                        count=pd.NamedAgg(column='contrast', aggfunc='count'),
                    )
                    .reset_index()
                )
                np.testing.assert_equal(trials_table['stim_probability_left'].values, 0.5)
                np.testing.assert_equal(np.unique(trials_table['reward_amount'].values), np.array([0, ADAPTIVE_REWARD]))
                np.testing.assert_equal(trials_table['training_phase'].values, training_phase)
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
                    assert np.sum(trials_table['debias_trial']) > 20
                else:
                    assert np.sum(trials_table['debias_trial']) == 0


class TestInstantiationTraining(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.task = TrainingChoiceWorldSession(**TASK_KWARGS)

    def test_task(self):
        trial_fixtures = get_fixtures()
        ADAPTIVE_REWARD = 1.9
        nt = 800
        task = TrainingChoiceWorldSession(**TASK_KWARGS, adaptive_reward=ADAPTIVE_REWARD)
        task.create_session()
        for i in np.arange(nt):
            task.next_trial()
            # pc = task.psychometric_curve()
            trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
            task.trial_completed(trial_fixtures[trial_type])
            if trial_type == 'correct':
                self.assertTrue(task.trials_table['trial_correct'][task.trial_num])
                self.assertEqual(task.trials_table['reward_amount'][task.trial_num], ADAPTIVE_REWARD)
            else:
                assert not task.trials_table['trial_correct'][task.trial_num]
            if i == 245:
                task.show_trial_log()
            assert not np.isnan(task.reward_time)

    def test_acquisition_description(self):
        ad = self.task.experiment_description
        ed = {
            'sync': {'bpod': {'collection': 'raw_task_data_00', 'extension': '.jsonable', 'acquisition_software': 'pybpod'}},
            'devices': {
                'cameras': {'left': {'collection': 'raw_video_data', 'sync_label': 'audio'}},
                'microphone': {'microphone': {'collection': 'raw_task_data_00', 'sync_label': 'audio'}},
            },
            'tasks': [
                {
                    '_iblrig_tasks_trainingChoiceWorld': {
                        'collection': 'raw_task_data_00',
                        'sync_label': 'bpod',
                        'extractors': ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus'],
                    }
                }
            ],
        }
        for k in ed:
            assert ad[k] == ed[k], f'Failed on {k}'
