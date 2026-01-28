import pandas as pd

import ibllib.pipes.dynamic_pipeline as dyn
from ibllib.pipes.behavior_tasks import PassiveTaskNidq
from iblrig.test.base import BaseTestCases
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession


class TestInstantiatePassiveChoiceWorld(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.session_id = 7
        self.get_task_kwargs()

        # NB: Passive choice world not supported with Bpod as main sync
        assert self.task_kwargs['hardware_settings']['MAIN_SYNC']
        with self.assertLogs('iblrig.task', 40):
            self.task = PassiveChoiceWorldSession(**self.task_kwargs, session_template_id=self.session_id)
        self.task_kwargs['hardware_settings']['MAIN_SYNC'] = False
        with self.assertNoLogs('iblrig.task', 40):
            self.task = PassiveChoiceWorldSession(**self.task_kwargs, session_template_id=self.session_id)
        self.task.mock()

    def test_fixtures(self) -> None:
        # assert that fixture are loaded correctly
        trials_table = self.task.trials_table
        assert trials_table.session_id.unique() == [self.session_id]
        pqt_file = self.task.get_task_directory().joinpath('passiveChoiceWorld_trials_fixtures.pqt')
        fixtures = pd.read_parquet(pqt_file)
        assert fixtures.session_id.unique().tolist() == list(range(12))
        assert fixtures[fixtures.session_id == self.session_id].stim_type.equals(trials_table.stim_type)

        # loop through fixtures
        for session_id in fixtures.session_id.unique():
            f = fixtures[fixtures.session_id == session_id]

            # The task stimuli replays consist of 300 stimulus presentations ordered randomly.
            assert len(f) == 300
            assert f.stim_type.iloc[:10].nunique() > 1
            assert set(f.stim_type.unique()) == {'G', 'N', 'T', 'V'}

            # 180 gabor patches with 300 ms duration
            # - 20 gabor patches with 0% contrast
            # - 20 gabor patches at 35 deg left side with 6.25%, 12.5%, 25%, 100% contrast (80 total)
            # - 20 gabor patches at 35 deg right side with 6.25%, 12.5%, 25%, 100% contrast (80 total)
            # 40 openings of the water valve
            # 40 go cues sounds
            # 40 noise bursts sounds
            assert len(f[f.stim_type == 'G']) == 180
            assert sum(f[f.stim_type == 'G'].contrast == 0.0) == 20
            positions = f[f.stim_type == 'G'].position.unique()
            assert set(positions) == {-35.0, 35.0}
            for position in positions:
                counts = f[(f.stim_type == 'G') & (f.position == position) & (f.contrast != 0.0)].contrast.value_counts()
                assert set(counts.keys()) == {0.0625, 0.125, 0.25, 1.0}
                assert all([v == 20 for v in counts.values])
            assert len(f[f.stim_type == 'V']) == 40
            assert len(f[f.stim_type == 'T']) == 40
            assert len(f[f.stim_type == 'N']) == 40

    def test_pipeline(self) -> None:
        """Test passive pipeline creation.

        In order for this to work we must add an external sync to the experiment description as
        Bpod only passive choice world is currently not supported.
        """
        self.task.experiment_description['sync'] = dyn.get_acquisition_description('ephys')['sync']
        self.task.create_session()
        pipeline = dyn.make_pipeline(self.task.paths.SESSION_FOLDER)
        self.assertIn('PassiveRegisterRaw_00', pipeline.tasks)
        self.assertIn('Trials_PassiveTaskNidq_00', pipeline.tasks)
        self.assertIsInstance(pipeline.tasks['Trials_PassiveTaskNidq_00'], PassiveTaskNidq)
