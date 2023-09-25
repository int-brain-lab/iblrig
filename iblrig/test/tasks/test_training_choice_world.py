import numpy as np

from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig.test.tasks.test_biased_choice_world_family import get_fixtures


class TestInstantiationTraining(BaseTestCases.CommonTestInstantiateTask):

    def setUp(self) -> None:
        self.task = TrainingChoiceWorldSession(**TASK_KWARGS)

    def test_task(self):
        trial_fixtures = get_fixtures()
        nt = 800
        for training_phase in np.arange(6):
            task = TrainingChoiceWorldSession(**TASK_KWARGS)
            task.training_phase = training_phase
            task.create_session()
            for i in np.arange(nt):
                task.next_trial()
                # pc = task.psychometric_curve()
                trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[.9, .05, .05])
                task.trial_completed(trial_fixtures[trial_type])
                if trial_type == 'correct':
                    assert task.trials_table['trial_correct'][task.trial_num]
                else:
                    assert not task.trials_table['trial_correct'][task.trial_num]
                if i == 245:
                    task.show_trial_log()
                assert not np.isnan(task.reward_time)

    def test_acquisition_description(self):
        ad = self.task.experiment_description
        ed = {
            'sync': {
                'bpod': {'collection': 'raw_task_data_00', 'extension': '.jsonable', 'acquisition_software': 'pybpod'}
            },
            'devices': {
                'cameras': {'left': {'collection': 'raw_video_data', 'sync_label': 'audio'}},
                'microphone': {'microphone': {'collection': 'raw_task_data_00', 'sync_label': 'audio'}},
            },
            'tasks': [{
                '_iblrig_tasks_trainingChoiceWorld': {
                    'collection': 'raw_task_data_00',
                    'sync_label': 'bpod',
                    'extractors': ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']}}
            ],
        }
        for k in ed:
            assert ad[k] == ed[k], f"Failed on {k}"
