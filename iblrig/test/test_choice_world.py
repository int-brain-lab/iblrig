"""
Unit tests for task logic functions
"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import iblrig.choiceworld
from iblrig import session_creator
from iblrig.path_helper import iterate_previous_sessions
from iblrig.raw_data_loaders import load_task_jsonable
from iblrig.test.base import TASK_KWARGS
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession
from iblrig_tasks._iblrig_tasks_spontaneous.task import Session as SpontaneousSession
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession


class TestGetPreviousSession(unittest.TestCase):
    def setUp(self) -> None:
        self.kwargs = copy.deepcopy(TASK_KWARGS)
        self.kwargs.update({'subject_weight_grams': 25})
        self.td = tempfile.TemporaryDirectory()
        self.root_path = Path(self.td.name)
        self.kwargs['iblrig_settings'] = dict(iblrig_local_data_path=self.root_path, ALYX_LAB='cortexlab')
        self.sesa = SpontaneousSession(**self.kwargs)
        self.sesa.create_session()
        self.sesb = TrainingChoiceWorldSession(**self.kwargs)
        # we make sure that the session has more than 42 trials in the settings, here sesd
        # is not returned as it is a dud with no trial and we expect 1 session in history: sesb
        self.sesb.session_info['NTRIALS'] = 400
        self.sesb.create_session()
        self.sesc = PassiveChoiceWorldSession(**self.kwargs)
        self.sesc.create_session()
        self.sesd = TrainingChoiceWorldSession(**self.kwargs)
        self.sesd.create_session()

    def test_iterate_previous_sessions(self):
        previous_sessions = iterate_previous_sessions(
            self.kwargs['subject'],
            task_name='_iblrig_tasks_trainingChoiceWorld',
            local_path=Path(self.root_path),
            lab='cortexlab',
            n=2,
        )
        self.assertEqual(len(previous_sessions), 1)
        # here we create a remote path, and copy over the sessions
        # then sesb is removed from the local server and sesd gets completed
        # we expect sesb from the remote server and sesd from the local server in history
        with tempfile.TemporaryDirectory() as tdd:
            shutil.copytree(self.root_path.joinpath('cortexlab'), tdd, dirs_exist_ok=True)
            shutil.rmtree(self.sesb.paths['SESSION_FOLDER'])
            self.sesd.session_info['NTRIALS'] = 400
            self.sesd.save_task_parameters_to_json_file()
            previous_sessions = iterate_previous_sessions(
                self.kwargs['subject'],
                task_name='_iblrig_tasks_trainingChoiceWorld',
                local_path=self.root_path,
                remote_path=Path(tdd),
                lab='cortexlab',
                n=2,
            )
            # we expect 2 sessions, one from the local data path and one from the remote
            self.assertEqual(len(previous_sessions), 2)
            self.assertEqual(len(set([ps['session_path'].parents[3] for ps in previous_sessions])), 2)

    @staticmethod
    def mock_jsonable(file_path, training_phase=3, reward_amount=None):
        file_fixtures = Path(__file__).parent.joinpath('fixtures', 'task_data_short.jsonable')
        trials_table, bpod_data = load_task_jsonable(file_fixtures)
        trials_table['training_phase'] = training_phase
        if file_path.exists():
            file_path.unlink()
        if reward_amount:
            trials_table['reward_amount'] = reward_amount / trials_table.shape[0]
        for i, trial in trials_table.iterrows():
            save_dict = trial.to_dict()
            save_dict['behavior_data'] = bpod_data[i]
            with open(file_path, 'a') as fp:
                fp.write(json.dumps(save_dict) + '\n')

    def test_adaptive_training_level(self):
        """
        Makes sure that when we create new sessions, the statuses are recovered properly from previous data
        :return:
        """
        self.mock_jsonable(self.sesb.paths.DATA_FILE_PATH, training_phase=2, reward_amount=1050)
        self.sesb.session_info['ADAPTIVE_REWARD_AMOUNT_UL'] = 2.1
        self.sesb.session_info['SUBJECT_WEIGHT'] = 17

        self.sesb.save_task_parameters_to_json_file()
        # test the function entry point
        tinfo, info = iblrig.choiceworld.get_subject_training_info(
            self.kwargs['subject'], local_path=Path(self.root_path), lab='cortexlab', mode='raise'
        )
        self.assertEqual((2, 2.1), (tinfo['training_phase'], tinfo['adaptive_reward']))
        self.assertIsInstance(info, dict)

        # test the task instantiation, should be the same as above
        t = TrainingChoiceWorldSession(**self.kwargs, training_phase=4, adaptive_reward=2.9, adaptive_gain=6.0)
        result = (t.training_phase, t.session_info['ADAPTIVE_REWARD_AMOUNT_UL'], t.session_info['ADAPTIVE_GAIN_VALUE'])
        self.assertEqual((4, 2.9, 6.0), result)
        # using the method we should get the same as above
        self.assertEqual(t.get_subject_training_info(), (2, 2.1, 4.0))
        # now the mouse is underfed
        self.sesb.session_info['ADAPTIVE_GAIN_VALUE'] = 5.0
        self.sesb.save_task_parameters_to_json_file()
        self.mock_jsonable(self.sesb.paths.DATA_FILE_PATH, training_phase=1, reward_amount=500)
        result = t.get_subject_training_info()
        self.assertEqual((1, 2.2, 5.0), result)

    def tearDown(self) -> None:
        self.td.cleanup()


class TestAdaptiveReward(unittest.TestCase):
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
        pc, _ = session_creator.make_ephysCW_pc()
        c = self.count_contrasts(pc)
        assert np.all(np.abs(1 - c * 9) <= 0.2)

    def test_biased(self):
        # test biased, signed contrasts are uniform
        np.random.seed(7816)
        pc, _ = session_creator.make_ephysCW_pc(prob_type='biased')
        c = self.count_contrasts(pc)
        assert np.all(np.abs(1 - c * 9) <= 0.2)

    def test_uniform(self):
        # test uniform: signed contrasts are twice as likely for the 0 sample
        pc, _ = session_creator.make_ephysCW_pc(prob_type='uniform')
        c = self.count_contrasts(pc)
        c[4] /= 2
        assert np.all(np.abs(1 - c * 10) <= 0.2)
