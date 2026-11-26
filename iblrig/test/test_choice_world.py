"""
Unit tests for task logic functions
"""

import json
import shutil
import tempfile
import unittest
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import iblrig.choiceworld
from iblrig import session_creator
from iblrig.base_choice_world import (
    ActiveChoiceWorldSession,
    BiasedChoiceWorldSession,
    ChoiceWorldSession,
    HabituationChoiceWorldSession,
    get_exit_state_timer,
)
from iblrig.path_helper import SessionInfo, iterate_previous_sessions
from iblrig.raw_data_loaders import load_task_jsonable
from iblrig.test.base import BaseTestCases
from iblrig_tasks._iblrig_tasks_passiveChoiceWorld.task import Session as PassiveChoiceWorldSession
from iblrig_tasks._iblrig_tasks_spontaneous.task import Session as SpontaneousSession
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from pybpodapi.protocol import StateMachine


class TestGetPreviousSession(BaseTestCases.CommonTestTask):
    def setUp(self) -> None:
        self.get_task_kwargs()
        self.task_kwargs.update({'subject_weight_grams': 25})
        self.session_a = SpontaneousSession(**self.task_kwargs)
        self.session_a.create_session()

        self.session_b = TrainingChoiceWorldSession(**self.task_kwargs)
        # we make sure that the session has more than 42 trials in the settings, here session_d
        # is not returned as it is a dud with no trial and we expect 1 session in history: session_b
        self.session_b.session_info['NTRIALS'] = 400
        self.session_b.create_session()

        self.session_c = PassiveChoiceWorldSession(**self.task_kwargs)
        self.session_c.create_session()

        # QUESTION: this will currently return default values as the jsonable of session_b cannot be found.
        #           Is this intended as such?
        self.session_d = TrainingChoiceWorldSession(**self.task_kwargs)
        self.session_d.create_session()

    def test_iterate_previous_sessions(self):
        previous_sessions = iterate_previous_sessions(
            self.task_kwargs['subject'],
            task_name='_iblrig_tasks_trainingChoiceWorld',
            local_path=self.tmp,
            lab='cortexlab',
            n=2,
            iblrig_settings=self.task_kwargs['iblrig_settings'],
        )
        self.assertEqual(len(previous_sessions), 1)
        # here we create a remote path, and copy over the sessions
        # then session_b is removed from the local server and session_d gets completed
        # we expect session_b from the remote server and session_d from the local server in history
        with tempfile.TemporaryDirectory() as tdd:
            shutil.copytree(self.tmp.joinpath('cortexlab'), tdd, dirs_exist_ok=True)
            shutil.rmtree(self.session_b.paths['SESSION_FOLDER'])
            self.session_d.session_info['NTRIALS'] = 400
            self.session_d.save_task_parameters_to_json_file()
            previous_sessions = iterate_previous_sessions(
                self.task_kwargs['subject'],
                task_name='_iblrig_tasks_trainingChoiceWorld',
                local_path=self.tmp,
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
        """
        self.mock_jsonable(self.session_b.paths.DATA_FILE_PATH, training_phase=2, reward_amount=1050)
        self.session_b.session_info['ADAPTIVE_REWARD_AMOUNT_UL'] = 2.1
        self.session_b.session_info['SUBJECT_WEIGHT'] = 17
        self.session_b.save_task_parameters_to_json_file()

        # test the function entry point
        training_info, session_info = iblrig.choiceworld.get_subject_training_info(
            self.task_kwargs['subject'],
            local_path=Path(self.tmp),
            lab='cortexlab',
            mode='raise',
            iblrig_settings=self.session_b.iblrig_settings,
        )
        self.assertEqual((2, 2.1), (training_info['training_phase'], training_info['adaptive_reward']))
        self.assertIsInstance(session_info, SessionInfo)

        # test the task instantiation
        t = TrainingChoiceWorldSession(**self.task_kwargs, training_phase=4, adaptive_reward=2.9, adaptive_gain=6.0)
        result = (t.training_phase, t.session_info['ADAPTIVE_REWARD_AMOUNT_UL'], t.session_info['ADAPTIVE_GAIN_VALUE'])
        self.assertEqual((4, 2.9, 6.0), result)

        # no previous session -> should return default values with gain = AG_INIT_VALUE
        with patch('iblrig.choiceworld.iterate_previous_sessions', sreturn_value=[]):
            self.assertEqual(
                (iblrig.choiceworld.DEFAULT_TRAINING_PHASE, t.task_params.REWARD_AMOUNT_UL, t.task_params.AG_INIT_VALUE),
                t.get_subject_training_info(),
            )

        # previous session with < 200 correct trials -> should return adaptive gain AG_INIT_VALUE = 8
        self.assertEqual((2, 2.1, t.task_params.AG_INIT_VALUE), t.get_subject_training_info())
        self.assertEqual(8, t.task_params.AG_INIT_VALUE)

        # previous session with > 200 correct trials -> should return adaptive gain of STIM_GAIN = 4
        with patch('iblrig.choiceworld.np.sum', return_value=400) as mock_sum:
            self.assertEqual((2, 2.1, t.task_params.STIM_GAIN), t.get_subject_training_info())
            mock_sum.assert_called_once()
            self.assertEqual(t.task_params.STIM_GAIN, 4)

        # exception while getting previous session -> should return default values with gain = STIM_GAIN
        with patch('iblrig.choiceworld.iterate_previous_sessions', side_effect=Exception()):
            self.assertEqual(
                (iblrig.choiceworld.DEFAULT_TRAINING_PHASE, t.task_params.REWARD_AMOUNT_UL, t.task_params.STIM_GAIN),
                t.get_subject_training_info(),
            )

        # now the mouse is underfed
        self.session_b.session_info['ADAPTIVE_GAIN_VALUE'] = 5.0
        self.session_b.save_task_parameters_to_json_file()
        self.mock_jsonable(self.session_b.paths.DATA_FILE_PATH, training_phase=1, reward_amount=500)
        result = t.get_subject_training_info()
        self.assertEqual((1, 2.2, 5.0), result)


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
        pc, _ = session_creator.make_ephyscw_pc()
        c = self.count_contrasts(pc)
        assert np.all(np.abs(1 - c * 9) <= 0.2)

    def test_biased(self):
        # test biased, signed contrasts are uniform
        np.random.seed(7816)
        pc, _ = session_creator.make_ephyscw_pc(prob_type='biased')
        c = self.count_contrasts(pc)
        assert np.all(np.abs(1 - c * 9) <= 0.2)

    def test_uniform(self):
        # test uniform: signed contrasts are twice as likely for the 0 sample
        pc, _ = session_creator.make_ephyscw_pc(prob_type='uniform')
        c = self.count_contrasts(pc)
        c[4] /= 2
        assert np.all(np.abs(1 - c * 10) <= 0.2)


class TestTrainingPhases(unittest.TestCase):
    def test_training_contrasts_probabilities(self):
        for phase in range(6):
            p = iblrig.choiceworld.training_contrasts_probabilities(phase)
            self.assertEqual(len(np.unique(p[p != 0])), 1)
            self.assertAlmostEqual(np.sum(p), 1)
            contrasts = np.unique(np.abs(iblrig.choiceworld.CONTRASTS[p > 0]))
            match phase:
                case 0:
                    assert np.array_equal(contrasts, [0.5, 1.0])
                case 1:
                    assert np.array_equal(contrasts, [0.25, 0.5, 1.0])
                case 2:
                    assert np.array_equal(contrasts, [0.125, 0.25, 0.5, 1.0])
                case 3:
                    assert np.array_equal(contrasts, [0.0625, 0.125, 0.25, 0.5, 1.0])
                case 4:
                    assert np.array_equal(contrasts, [0.0, 0.0625, 0.125, 0.25, 0.5, 1.0])
                case 5:
                    assert np.array_equal(contrasts, [0.0, 0.0625, 0.125, 0.25, 1.0])
        with self.assertRaises(ValueError):
            iblrig.choiceworld.training_contrasts_probabilities(6)

    def test_training_phase_from_contrast_set(self):
        for phase in range(6):
            p = iblrig.choiceworld.training_contrasts_probabilities(phase)
            contrasts1 = iblrig.choiceworld.CONTRASTS[p > 0]
            contrasts2 = np.abs(contrasts1)
            contrasts3 = np.unique(contrasts2)
            self.assertEqual(iblrig.choiceworld.training_phase_from_contrast_set(contrasts1), phase)
            self.assertEqual(iblrig.choiceworld.training_phase_from_contrast_set(contrasts2), phase)
            self.assertEqual(iblrig.choiceworld.training_phase_from_contrast_set(contrasts3), phase)
        with self.assertRaises(ValueError):
            iblrig.choiceworld.training_phase_from_contrast_set([0.666])


class _ChannelNames(list):
    """Stand-in for Bpod's channel/event name tables: ``index`` registers unknown names, giving each a distinct code."""

    def index(self, name, *args):
        if name not in self:
            self.append(name)
        return super().index(name, *args)


class _Actions:
    """Stand-in for ``Bpod.actions``: every action is a valid (name, value) output tuple."""

    def __getattr__(self, name):
        return ('SoftCode', 1)


def make_bpod(mocker):
    """A mocked Bpod with channel tables that are sufficient for building a real StateMachine."""
    bpod = mocker.MagicMock()
    bpod.hardware.max_states = 128
    bpod.hardware.channels = SimpleNamespace(
        event_names=_ChannelNames(),
        output_channel_names=_ChannelNames(),
        events_positions=SimpleNamespace(globalTimerTrigger=-1, globalTimerCancel=-2),
    )
    bpod.actions = _Actions()
    return bpod


class TestITI:
    @pytest.fixture(
        params=[
            ChoiceWorldSession,
            HabituationChoiceWorldSession,
            ActiveChoiceWorldSession,
            BiasedChoiceWorldSession,
            TrainingChoiceWorldSession,
        ]
    )
    def session_and_sma(self, request, mocker):
        bpod = make_bpod(mocker)

        def _factory(n_trials: int):
            session_class = request.param

            # Real StateMachine on a mocked Bpod, spying on add_state
            sma = StateMachine(bpod)
            mocker.spy(sma, 'add_state')

            # Create autospec instance
            session = mocker.create_autospec(session_class, instance=True)
            session.bpod = bpod
            session.trials_table = mocker.MagicMock()
            session.trial_num = mocker.MagicMock()
            session.movement_left = mocker.MagicMock()
            session.movement_right = mocker.MagicMock()
            session.interactive = False  # a truthy mock would spawn the online plots subprocess (unpicklable on Windows)
            session.paths = mocker.MagicMock()

            # Restore real methods
            session._run = session_class._run.__get__(session, session_class)
            session.get_state_machine_trial = session_class.get_state_machine_trial.__get__(session, session_class)

            # Patch returned StateMachine
            session._instantiate_state_machine.return_value = sma
            mocker.patch('iblrig.base_choice_world.StateMachine', return_value=sma)

            # Minimal task parameters
            session.task_params = session_class.read_task_parameter_files()
            session.task_params['NTRIALS'] = n_trials
            session.paused = False
            session.stopped = False

            return session, sma

        return _factory

    @pytest.fixture
    def mock_sleep(self, mocker):
        return mocker.patch('iblrig.base_choice_world.time.sleep')

    @pytest.fixture
    def mock_perf_counter(self, mocker):
        def _factory(period: float):
            return mocker.patch('iblrig.base_choice_world.time.perf_counter', side_effect=count(0, period))

        return _factory

    def test_last_state_duration(self, session_and_sma, mock_sleep, caplog):
        """The last state should be 0.5 s in duration."""
        session, sma = session_and_sma(n_trials=1)
        session._run()
        last_state_duration = sma.add_state.call_args_list[-1].kwargs['state_timer']
        assert last_state_duration == 0.5, 'Last state should be 0.5 s in length'

    def test_last_state_duration_warning(self, session_and_sma, mock_sleep, caplog):
        """If the last state is not 0.5 s in duration, a warning should be logged."""
        session, sma = session_and_sma(n_trials=1)
        session.task_params['ITI_DELAY_SECS'] = 0.3  # the exit state's timer is min(0.5, ITI_DELAY_SECS)
        session._run()
        assert "The last state ('exit_state') had a duration of 0.3 s. It should be exactly 0.5 s." in caplog.text

    def test_iti_components(self, session_and_sma, mock_sleep, mock_perf_counter, caplog):
        """Test if ITI components are computed correctly."""
        session, sma = session_and_sma(n_trials=2)
        iti_delay_processing = 0.4321
        mock_perf_counter(period=iti_delay_processing)
        session._run()
        iti_delay_sma = sma.add_state.call_args_list[-1].kwargs['state_timer']
        iti_delay_sleep = mock_sleep.call_args[0][0] if mock_sleep.call_args else 0.0
        assert ('BNC1', 255) in sma.add_state.call_args_list[-1].kwargs['output_actions'], 'Last state should raise BNC1'
        assert mock_sleep.called, 'Sleep should be called'
        assert pytest.approx(iti_delay_sma + iti_delay_processing + iti_delay_sleep, rel=1e-6) == 1.0, 'Total ITI should be 1.0 s'

    def test_warning_when_iti_too_high(self, session_and_sma, mock_sleep, mock_perf_counter, caplog):
        """Test if larger than intended ITI is logged with a warning."""
        session, sma = session_and_sma(n_trials=2)
        mock_perf_counter(period=0.6)
        session._run()
        assert 'Actual ITI: 1.1' in caplog.text
        assert not mock_sleep.called, 'Sleep should not be called'


BNC1 = [('BNC1', 255)]

# (state_name, state_timer, destination of 'Tup'); states transitioning to 'exit' raise BNC1
EXIT_STATE_LAYOUTS = {
    'exit_state_last': [('a', 1.0, 'exit_state'), ('exit_state', 0.5, 'exit')],
    'state_after_exit_state': [('a', 1.0, 'exit_state'), ('exit_state', 0.5, 'exit'), ('late', 9.0, 'a')],
    'exit_state_not_named_exit_state': [('a', 1.0, 'b'), ('b', 0.5, 'exit'), ('c', 9.0, 'a')],
    'repeated_state_names': [('a', 1.0, 'exit_state'), ('a', 2.0, 'exit_state'), ('exit_state', 0.5, 'exit')],
    'several_exit_states_same_timer': [('a', 0.5, 'exit'), ('b', 0.5, 'exit'), ('c', 9.0, 'a')],
}


def add_states(sma, layout, exit_actions=BNC1):
    for name, timer, destination in layout:
        sma.add_state(
            state_name=name,
            state_timer=timer,
            state_change_conditions={'Tup': destination},
            output_actions=exit_actions if destination == 'exit' else [],
        )


class TestGetExitStateTimer:
    @pytest.fixture
    def sma(self, mocker):
        return StateMachine(make_bpod(mocker))

    @pytest.mark.parametrize('layout', EXIT_STATE_LAYOUTS.values(), ids=EXIT_STATE_LAYOUTS.keys())
    def test_exit_state_timer(self, sma, caplog, layout):
        add_states(sma, layout)
        assert get_exit_state_timer(sma) == 0.5
        assert not caplog.text

    def test_no_exit_state(self, sma):
        add_states(sma, [('a', 1.0, 'a')])
        with pytest.raises(ValueError, match=r'no state transitioning'):
            get_exit_state_timer(sma)

    def test_multiple_exit_states_differing_timers(self, sma):
        add_states(sma, [('a', 1.0, 'exit'), ('b', 0.5, 'exit')])
        with pytest.raises(ValueError, match=r"differing timers: \{'a': 1.0, 'b': 0.5\}"):
            get_exit_state_timer(sma)

    @pytest.mark.parametrize('value', [1, 255])
    def test_exit_state_with_bnc1_any_positive_value(self, sma, value):
        add_states(sma, EXIT_STATE_LAYOUTS['exit_state_last'], exit_actions=[('BNC1', value)])
        assert get_exit_state_timer(sma) == 0.5

    @pytest.mark.parametrize('exit_actions', [[], [('BNC1', 0)], [('BNC2', 255)]])
    def test_exit_state_without_bnc1(self, sma, exit_actions):
        add_states(sma, EXIT_STATE_LAYOUTS['exit_state_last'], exit_actions=exit_actions)
        with pytest.raises(ValueError, match=r'must raise BNC1.*exit_state'):
            get_exit_state_timer(sma)

    def test_one_of_several_exit_states_without_bnc1(self, sma):
        sma.add_state(state_name='a', state_timer=0.5, state_change_conditions={'Tup': 'exit'}, output_actions=BNC1)
        sma.add_state(state_name='b', state_timer=0.5, state_change_conditions={'Tup': 'exit'})
        with pytest.raises(ValueError, match=r"must raise BNC1.*\['b'\]"):
            get_exit_state_timer(sma)

    @pytest.mark.parametrize(
        ('event', 'destination', 'warns'),
        [
            ('BNC1High', 'exit', True),
            ('GlobalTimer1_End', 'exit', True),
            ('GlobalTimer1_Start', 'exit', True),
            ('GlobalCounter1_End', 'exit', True),
            ('Condition1', 'exit', True),
            ('BNC1High', 'exit_state', False),  # not a transition to 'exit'
            ('GlobalTimerTrig', 1, False),  # pybpod stores an int (not a list of transitions) for these events
            ('GlobalTimerCancel', 1, False),
        ],
    )
    def test_warning_on_non_tup_transition_to_exit(self, sma, caplog, event, destination, warns):
        sma.add_state(state_name='a', state_timer=1.0, state_change_conditions={'Tup': 'exit_state', event: destination})
        sma.add_state(state_name='exit_state', state_timer=0.5, state_change_conditions={'Tup': 'exit'}, output_actions=BNC1)
        assert get_exit_state_timer(sma) == 0.5
        if warns:
            assert "['a'] transition to 'exit' on an event other than 'Tup'" in caplog.text
        else:
            assert not caplog.text

    def test_warning_if_timer_is_not_half_a_second(self, sma, caplog):
        add_states(sma, [('a', 1.0, 'exit_state'), ('exit_state', 0.3, 'exit')])
        assert get_exit_state_timer(sma) == 0.3
        assert "The last state ('exit_state') had a duration of 0.3 s. It should be exactly 0.5 s." in caplog.text
