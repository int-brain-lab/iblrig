"""
Unit tests for task logic functions
"""
from pathlib import Path
import unittest
import copy
import tempfile
import shutil

import numpy as np
import pandas as pd

from iblrig.test.base import TASK_KWARGS
from iblrig import session_creator
import iblrig.choiceworld
from iblrig.path_helper import iterate_previous_sessions
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession
from iblrig_tasks._iblrig_tasks_spontaneous.task import Session as SpontaneousSession


class TestGetPreviousSession(unittest.TestCase):

    def test_get_previous_session(self):
        # zip_file = Path(__file__).parent.joinpath('fixtures', 'training_cw_iblrigv8.zip')
        kwargs = copy.deepcopy(TASK_KWARGS)
        with tempfile.TemporaryDirectory() as td:
            kwargs['iblrig_settings'] = dict(iblrig_local_data_path=Path(td))
            sesa = SpontaneousSession(**kwargs)
            sesa.create_session()
            sesb = TrainingChoiceWorldSession(**kwargs)
            sesb.create_session()
            sesc = PassiveChoiceWorldSession(**kwargs)
            sesc.create_session()
            sesd = TrainingChoiceWorldSession(**kwargs)
            sesd.create_session()
            # we make sure that the session has more than 42 trials in the settings, here sesd
            # is not returned as it is a dud with no trial and we expect 1 session in history: sesb
            sesb.session_info['NTRIALS'] = 400
            sesb.save_task_parameters_to_json_file()
            previous_sessions = iterate_previous_sessions(
                kwargs['subject'], task_name='_iblrig_tasks_trainingChoiceWorld',
                local_path=Path(td), lab='cortexlab', n=2)
            self.assertEqual(len(previous_sessions), 1)
            # here we create a remote path, and copy over the sessions
            # then sesb is removed from the local server and sesd gets completed
            # we expect sesb from the remote server and sesd from the local server in history
            with tempfile.TemporaryDirectory() as tdd:
                shutil.copytree(Path(td).joinpath('cortexlab'), tdd, dirs_exist_ok=True)
                shutil.rmtree(sesb.paths['SESSION_FOLDER'])
                sesd.session_info['NTRIALS'] = 400
                sesd.save_task_parameters_to_json_file()
                previous_sessions = iterate_previous_sessions(
                    kwargs['subject'], task_name='_iblrig_tasks_trainingChoiceWorld',
                    local_path=Path(td), remote_path=Path(tdd), lab='cortexlab', n=2)
                # we expect 2 sessions, one from the local data path and one from the remote
                self.assertEqual(len(previous_sessions), 2)
                self.assertEqual(len(set([ps['session_path'].parents[3] for ps in previous_sessions])), 2)

    def test_adaptive_reward(self):
        fixture = (
            ((25, 3, 1234, 399), 2.9),
            ((25, 3, 1234, 123), 3.0),
            ((25, 2.3, 234, 123), 2.4),
            ((25, 3, 234, 123), 3),
            ((25, 1.5, 1234, 423), 1.5),
        )

        for args, expected in fixture:
            print(args, expected)
            with self.subTest(args=args):
                self.assertEqual(expected, iblrig.choiceworld.compute_adaptive_reward_volume(*args))


class TestsBiasedBlocksGeneration(unittest.TestCase):

    @staticmethod
    def count_contrasts(pc):
        df = pd.DataFrame(data=pc, columns=['angle', 'contrast', 'proba'])
        df['signed_contrasts'] = df['contrast'] * np.sign(df['angle'])
        c = df.groupby('signed_contrasts')['signed_contrasts'].count() / pc.shape[0]
        return c.values

    def test_default(self):
        np.random.seed(7816)
        # the default generation has a bias on the 0-contrast
        pc, lb = session_creator.make_ephysCW_pc()
        c = self.count_contrasts(pc)
        assert np.all(np.abs(1 - c * 9) <= 0.2)

    def test_biased(self):
        # test biased, signed contrasts are uniform
        np.random.seed(7816)
        pc, lb = session_creator.make_ephysCW_pc(prob_type='biased')
        c = self.count_contrasts(pc)
        assert np.all(np.abs(1 - c * 9) <= 0.2)

    def test_uniform(self):
        # test uniform: signed contrasts are twice as likely for the 0 sample
        pc, lb = session_creator.make_ephysCW_pc(prob_type='uniform')
        c = self.count_contrasts(pc)
        c[4] /= 2
        assert np.all(np.abs(1 - c * 10) <= 0.2)
