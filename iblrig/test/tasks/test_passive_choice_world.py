import copy

import numpy as np

import ibllib.pipes.dynamic_pipeline as dyn
from ibllib.pipes.behavior_tasks import PassiveTaskNidq
from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession


class TestInstantiatePassiveChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        session_id = 7
        # NB: Passive choice world not supported with Bpod as main sync
        kwargs = copy.deepcopy(TASK_KWARGS)
        assert kwargs['hardware_settings']['MAIN_SYNC']
        with self.assertLogs('iblrig.task', 40):
            PassiveChoiceWorldSession(**kwargs, session_template_id=session_id)
        kwargs['hardware_settings']['MAIN_SYNC'] = False
        with self.assertNotLogs('iblrig.task', 40):
            self.task = PassiveChoiceWorldSession(**kwargs, session_template_id=session_id)
        self.task.mock()
        assert np.unique(self.task.trials_table['session_id']) == [session_id]

    def test_pipeline(self) -> None:
        """Test passive pipeline creation.

        In order for this to work we must add an external sync to the experiment description as
        Bpod only passive choice world is currently not supported.
        """
        self.task.experiment_description['sync'] = dyn.get_acquisition_description('choice_world_recording')['sync']
        self.task.create_session()
        pipeline = dyn.make_pipeline(self.task.paths.SESSION_FOLDER)
        self.assertIn('PassiveRegisterRaw_00', pipeline.tasks)
        self.assertIn('PassiveTaskNidq_00', pipeline.tasks)
        self.assertIsInstance(pipeline.tasks['PassiveTaskNidq_00'], PassiveTaskNidq)
