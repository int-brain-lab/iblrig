"""
This modules extends the base_tasks modules by providing task logic around the Choice World protocol
"""
import abc
import json
import math
import random
import subprocess
import time
import traceback
from pathlib import Path
from string import ascii_letters
from typing import Annotated, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

import iblrig.base_tasks
import iblrig.graphic
from iblrig import choiceworld, misc
from iblrig.hardware import SOFTCODE
from iblutil.io import jsonable
from iblutil.util import Bunch, setup_logger
from pybpodapi.com.messaging.trial import Trial
from pybpodapi.protocol import StateMachine

log = setup_logger('iblrig')

NTRIALS_INIT = 2000
NBLOCKS_INIT = 100

Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class ChoiceWorldParams(BaseModel):
    AUTOMATIC_CALIBRATION: bool = True
    ADAPTIVE_REWARD: bool = False
    BONSAI_EDITOR: bool = False
    CALIBRATION_VALUE: float = 0.067
    CONTRAST_SET: list[Probability] = Field([1.0, 0.25, 0.125, 0.0625, 0.0], min_items=1)
    CONTRAST_SET_PROBABILITY_TYPE: Literal['uniform', 'skew_zero'] = 'uniform'
    GO_TONE_AMPLITUDE: float = 0.0272
    GO_TONE_DURATION: float = 0.11
    GO_TONE_IDX: int = Field(2, ge=0)
    GO_TONE_FREQUENCY: float = Field(5000, gt=0)
    FEEDBACK_CORRECT_DELAY_SECS: float = 1
    FEEDBACK_ERROR_DELAY_SECS: float = 2
    FEEDBACK_NOGO_DELAY_SECS: float = 2
    INTERACTIVE_DELAY: float = 0.0
    ITI_DELAY_SECS: float = 1
    NTRIALS: int = Field(2000, gt=0)
    POOP_COUNT: bool = True
    PROBABILITY_LEFT: Probability = 0.5
    QUIESCENCE_THRESHOLDS: list[float] = Field(default=[-2, 2], min_length=2, max_length=2)
    QUIESCENT_PERIOD: float = 0.2
    RECORD_AMBIENT_SENSOR_DATA: bool = True
    RECORD_SOUND: bool = True
    RESPONSE_WINDOW: float = 60
    REWARD_AMOUNT_UL: float = 1.5
    REWARD_TYPE: str = 'Water 10% Sucrose'
    STIM_ANGLE: float = 0.0
    STIM_FREQ: float = 0.1
    STIM_GAIN: float = 4.0  # wheel to stimulus relationship (degrees visual angle per mm of wheel displacement)
    STIM_POSITIONS: list[float] = [-35, 35]
    STIM_SIGMA: float = 7.0
    STIM_TRANSLATION_Z: Literal[7, 8] = 7  # 7 for ephys, 8 otherwise. -p:Stim.TranslationZ-{STIM_TRANSLATION_Z} bonsai parameter
    SYNC_SQUARE_X: float = 1.33
    SYNC_SQUARE_Y: float = -1.03
    USE_AUTOMATIC_STOPPING_CRITERIONS: bool = True
    VISUAL_STIMULUS: str = 'GaborIBLTask / Gabor2D.bonsai'  # null / passiveChoiceWorld_passive.bonsai
    WHITE_NOISE_AMPLITUDE: float = 0.05
    WHITE_NOISE_DURATION: float = 0.5
    WHITE_NOISE_IDX: int = 3


class ChoiceWorldSession(
    iblrig.base_tasks.BaseSession,
    iblrig.base_tasks.BonsaiRecordingMixin,
    iblrig.base_tasks.BonsaiVisualStimulusMixin,
    iblrig.base_tasks.BpodMixin,
    iblrig.base_tasks.Frame2TTLMixin,
    iblrig.base_tasks.RotaryEncoderMixin,
    iblrig.base_tasks.SoundMixin,
    iblrig.base_tasks.ValveMixin,
):
    # task_params = ChoiceWorldParams()
    base_parameters_file = Path(__file__).parent.joinpath('base_choice_world_params.yaml')

    def __init__(self, *args, delay_secs=0, **kwargs):
        super().__init__(**kwargs)
        self.task_params['SESSION_DELAY_START'] = delay_secs
        # init behaviour data
        self.movement_left = self.device_rotary_encoder.THRESHOLD_EVENTS[self.task_params.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = self.device_rotary_encoder.THRESHOLD_EVENTS[self.task_params.QUIESCENCE_THRESHOLDS[1]]
        # init counter variables
        self.trial_num = -1
        self.block_num = -1
        self.block_trial_num = -1
        # init the tables, there are 2 of them: a trials table and a ambient sensor data table
        self.trials_table = pd.DataFrame(
            {
                'contrast': np.zeros(NTRIALS_INIT) * np.NaN,
                'position': np.zeros(NTRIALS_INIT) * np.NaN,
                'quiescent_period': np.zeros(NTRIALS_INIT) * np.NaN,
                'response_side': np.zeros(NTRIALS_INIT, dtype=np.int8),
                'response_time': np.zeros(NTRIALS_INIT) * np.NaN,
                'reward_amount': np.zeros(NTRIALS_INIT) * np.NaN,
                'reward_valve_time': np.zeros(NTRIALS_INIT) * np.NaN,
                'stim_angle': np.zeros(NTRIALS_INIT) * np.NaN,
                'stim_freq': np.zeros(NTRIALS_INIT) * np.NaN,
                'stim_gain': np.zeros(NTRIALS_INIT) * np.NaN,
                'stim_phase': np.zeros(NTRIALS_INIT) * np.NaN,
                'stim_reverse': np.zeros(NTRIALS_INIT, dtype=bool),
                'stim_sigma': np.zeros(NTRIALS_INIT) * np.NaN,
                'trial_correct': np.zeros(NTRIALS_INIT, dtype=bool),
                'trial_num': np.zeros(NTRIALS_INIT, dtype=np.int16),
            }
        )

        self.ambient_sensor_table = pd.DataFrame(
            {
                'Temperature_C': np.zeros(NTRIALS_INIT) * np.NaN,
                'AirPressure_mb': np.zeros(NTRIALS_INIT) * np.NaN,
                'RelativeHumidity': np.zeros(NTRIALS_INIT) * np.NaN,
            }
        )

    @staticmethod
    def extra_parser():
        """:return: argparse.parser()"""
        parser = super(ChoiceWorldSession, ChoiceWorldSession).extra_parser()
        parser.add_argument(
            '--delay_secs',
            dest='delay_secs',
            default=0,
            type=int,
            required=False,
            help='initial delay before starting the first trial (default: 0s)',
        )
        return parser

    def start_hardware(self):
        """
        In this step we explicitly run the start methods of the various mixins.
        The super class start method is overloaded because we need to start the different hardware pieces in order
        """
        if not self.is_mock:
            self.start_mixin_frame2ttl()
            self.start_mixin_bpod()
            self.start_mixin_valve()
            self.start_mixin_sound()
            self.start_mixin_rotary_encoder()
            self.start_mixin_bonsai_cameras()
            self.start_mixin_bonsai_microphone()
            self.start_mixin_bonsai_visual_stimulus()

    def _run(self):
        """
        This is the method that runs the task with the actual state machine
        :return:
        """
        # make the bpod send spacer signals to the main sync clock for protocol discovery
        self.send_spacers()
        time_last_trial_end = time.time()
        for i in range(self.task_params.NTRIALS):  # Main loop
            # t_overhead = time.time()
            self.next_trial()
            log.info(f'Starting trial: {i}')
            # =============================================================================
            #     Start state machine definition
            # =============================================================================
            sma = self.get_state_machine_trial(i)
            log.info('Sending state machine to bpod')
            # Send state machine description to Bpod device
            self.bpod.send_state_machine(sma)
            # t_overhead = time.time() - t_overhead
            # Run state machine
            dt = self.task_params.ITI_DELAY_SECS - 0.5 - (time.time() - time_last_trial_end)
            # wait to achieve the desired ITI duration
            if dt > 0:
                time.sleep(dt)
            log.info('running state machine')
            self.bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
            time_last_trial_end = time.time()
            self.trial_completed(self.bpod.session.current_trial.export())
            self.show_trial_log()
            while self.paths.SESSION_FOLDER.joinpath('.pause').exists():
                time.sleep(1)
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break

    def mock(self, file_jsonable_fixture=None):
        """
        This methods serves to instantiate a state machine and bpod object to simulate a taks run.
        This is useful to test or display the state machine flow
        """
        super().mock()

        if file_jsonable_fixture is not None:
            task_data = jsonable.read(file_jsonable_fixture)
            # pop-out the bpod data from the table
            bpod_data = []
            for td in task_data:
                bpod_data.append(td.pop('behavior_data'))

            class MockTrial(Trial):
                def export(self):
                    return np.random.choice(bpod_data)
        else:

            class MockTrial(Trial):
                def export(self):
                    return {}

        self.bpod.session.trials = [MockTrial()]
        self.bpod.send_state_machine = lambda k: None
        self.bpod.run_state_machine = lambda k: time.sleep(1.2)

        daction = ('dummy', 'action')
        self.sound = Bunch(
            {
                'GO_TONE': daction,
                'WHITE_NOISE': daction,
            }
        )

        self.bpod.actions.update(
            {
                'play_tone': daction,
                'play_noise': daction,
                'stop_sound': daction,
                'rotary_encoder_reset': daction,
                'bonsai_hide_stim': daction,
                'bonsai_show_stim': daction,
                'bonsai_closed_loop': daction,
                'bonsai_freeze_stim': daction,
                'bonsai_show_center': daction,
            }
        )

    def get_graphviz_task(self, output_file=None, view=True):
        """
        For a given task, outputs the state machine states diagram in Digraph format
        :param output_file:
        :return:
        """
        import graphviz

        self.next_trial()
        sma = self.get_state_machine_trial(0)
        if sma is None:
            return
        states_indices = {i: k for i, k in enumerate(sma.state_names)}
        states_indices.update({(i + 10000): k for i, k in enumerate(sma.undeclared)})
        states_letters = {k: ascii_letters[i] for i, k in enumerate(sma.state_names)}
        dot = graphviz.Digraph(comment='The Great IBL Task')
        edges = []

        for i in range(len(sma.state_names)):
            letter = states_letters[sma.state_names[i]]
            dot.node(letter, sma.state_names[i])
            if ~np.isnan(sma.state_timer_matrix[i]):
                out_state = states_indices[sma.state_timer_matrix[i]]
                edges.append(f'{letter}{states_letters[out_state]}')
            for input in sma.input_matrix[i]:
                if input[0] == 0:
                    edges.append(f'{letter}{states_letters[states_indices[input[1]]]}')
        dot.edges(edges)
        if output_file is not None:
            try:
                dot.render(output_file, view=view)
            except graphviz.exceptions.ExecutableNotFound:
                log.info('Graphviz system executable not found, cannot render the graph')
        return dot

    def get_state_machine_trial(self, i):
        sma = StateMachine(self.bpod)
        if i == 0:  # First trial exception start camera
            session_delay_start = self.task_params.get('SESSION_DELAY_START', 0)
            log.info('First trial initializing, will move to next trial only if:')
            log.info('1. camera is detected')
            log.info(f'2. {session_delay_start} sec have elapsed')
            sma.add_state(
                state_name='trial_start',
                state_timer=0,
                state_change_conditions={'Port1In': 'delay_initiation'},
                output_actions=[('SoftCode', SOFTCODE.TRIGGER_CAMERA), ('BNC1', 255)],
            )  # start camera
            sma.add_state(
                state_name='delay_initiation',
                state_timer=session_delay_start,
                output_actions=[],
                state_change_conditions={'Tup': 'reset_rotary_encoder'},
            )
        else:
            sma.add_state(
                state_name='trial_start',
                state_timer=0,  # ~100µs hardware irreducible delay
                state_change_conditions={'Tup': 'reset_rotary_encoder'},
                output_actions=[self.bpod.actions.stop_sound, ('BNC1', 255)],
            )  # stop all sounds

        sma.add_state(
            state_name='reset_rotary_encoder',
            state_timer=0,
            output_actions=[self.bpod.actions.rotary_encoder_reset],
            state_change_conditions={'Tup': 'quiescent_period'},
        )

        sma.add_state(  # '>back' | '>reset_timer'
            state_name='quiescent_period',
            state_timer=self.quiescent_period,
            output_actions=[],
            state_change_conditions={
                'Tup': 'stim_on',
                self.movement_left: 'reset_rotary_encoder',
                self.movement_right: 'reset_rotary_encoder',
            },
        )
        # show stimulus, move on to next state if a frame2ttl is detected, with a time-out of 0.1s
        sma.add_state(
            state_name='stim_on',
            state_timer=0.1,
            output_actions=[self.bpod.actions.bonsai_show_stim],
            state_change_conditions={
                'Tup': 'interactive_delay',
                'BNC1High': 'interactive_delay',
                'BNC1Low': 'interactive_delay',
            },
        )
        # this is a feature that can eventually add a delay between visual and auditory cue
        sma.add_state(
            state_name='interactive_delay',
            state_timer=self.task_params.INTERACTIVE_DELAY,
            output_actions=[],
            state_change_conditions={'Tup': 'play_tone'},
        )
        # play tone, move on to next state if sound is detected, with a time-out of 0.1s
        sma.add_state(
            state_name='play_tone',
            state_timer=0.1,
            output_actions=[self.bpod.actions.play_tone],
            state_change_conditions={
                'Tup': 'reset2_rotary_encoder',
                'BNC2High': 'reset2_rotary_encoder',
            },
        )

        sma.add_state(
            state_name='reset2_rotary_encoder',
            state_timer=0.05,  # the delay here is to avoid race conditions in the bonsai flow
            output_actions=[self.bpod.actions.rotary_encoder_reset],
            state_change_conditions={'Tup': 'closed_loop'},
        )

        sma.add_state(
            state_name='closed_loop',
            state_timer=self.task_params.RESPONSE_WINDOW,
            output_actions=[self.bpod.actions.bonsai_closed_loop],
            state_change_conditions={
                'Tup': 'no_go',
                self.event_error: 'freeze_error',
                self.event_reward: 'freeze_reward',
            },
        )

        sma.add_state(
            state_name='no_go',
            state_timer=self.task_params.FEEDBACK_NOGO_DELAY_SECS,
            output_actions=[self.bpod.actions.bonsai_hide_stim, self.bpod.actions.play_noise],
            state_change_conditions={'Tup': 'exit_state'},
        )

        sma.add_state(
            state_name='freeze_error',
            state_timer=0,
            output_actions=[self.bpod.actions.bonsai_freeze_stim],
            state_change_conditions={'Tup': 'error'},
        )

        sma.add_state(
            state_name='error',
            state_timer=self.task_params.FEEDBACK_ERROR_DELAY_SECS,
            output_actions=[self.bpod.actions.play_noise],
            state_change_conditions={'Tup': 'hide_stim'},
        )

        sma.add_state(
            state_name='freeze_reward',
            state_timer=0,
            output_actions=[self.bpod.actions.bonsai_freeze_stim],
            state_change_conditions={'Tup': 'reward'},
        )

        sma.add_state(
            state_name='reward',
            state_timer=self.reward_time,
            output_actions=[('Valve1', 255), ('BNC1', 255)],
            state_change_conditions={'Tup': 'correct'},
        )

        sma.add_state(
            state_name='correct',
            state_timer=self.task_params.FEEDBACK_CORRECT_DELAY_SECS,
            output_actions=[],
            state_change_conditions={'Tup': 'hide_stim'},
        )

        sma.add_state(
            state_name='hide_stim',
            state_timer=0.1,
            output_actions=[self.bpod.actions.bonsai_hide_stim],
            state_change_conditions={
                'Tup': 'exit_state',
                'BNC1High': 'exit_state',
                'BNC1Low': 'exit_state',
            },
        )

        sma.add_state(
            state_name='exit_state',
            state_timer=self.task_params.ITI_DELAY_SECS,
            output_actions=[('BNC1', 255)],
            state_change_conditions={'Tup': 'exit'},
        )
        return sma

    @abc.abstractmethod
    def next_trial(self):
        pass

    @property
    def reward_amount(self):
        return self.task_params.REWARD_AMOUNT_UL

    def draw_next_trial_info(self, pleft=0.5, contrast=None, position=None):
        if contrast is None:
            contrast = misc.draw_contrast(self.task_params.CONTRAST_SET, self.task_params.CONTRAST_SET_PROBABILITY_TYPE)
        assert len(self.task_params.STIM_POSITIONS) == 2, 'Only two positions are supported'
        position = position or int(np.random.choice(self.task_params.STIM_POSITIONS, p=[pleft, 1 - pleft]))
        quiescent_period = self.task_params.QUIESCENT_PERIOD + misc.truncated_exponential(
            scale=0.35, min_value=0.2, max_value=0.5
        )
        self.trials_table.at[self.trial_num, 'quiescent_period'] = quiescent_period
        self.trials_table.at[self.trial_num, 'contrast'] = contrast
        self.trials_table.at[self.trial_num, 'stim_phase'] = random.uniform(0, 2 * math.pi)
        self.trials_table.at[self.trial_num, 'stim_sigma'] = self.task_params.STIM_SIGMA
        self.trials_table.at[self.trial_num, 'stim_angle'] = self.task_params.STIM_ANGLE
        self.trials_table.at[self.trial_num, 'stim_gain'] = self.task_params.STIM_GAIN
        self.trials_table.at[self.trial_num, 'stim_freq'] = self.task_params.STIM_FREQ
        self.trials_table.at[self.trial_num, 'trial_num'] = self.trial_num
        self.trials_table.at[self.trial_num, 'position'] = position
        self.trials_table.at[self.trial_num, 'reward_amount'] = self.reward_amount
        self.trials_table.at[self.trial_num, 'stim_probability_left'] = pleft
        self.send_trial_info_to_bonsai()

    def trial_completed(self, bpod_data):
        # if the reward state has not been triggered, null the reward
        if np.isnan(bpod_data['States timestamps']['reward'][0][0]):
            self.trials_table.at[self.trial_num, 'reward_amount'] = 0
        self.trials_table.at[self.trial_num, 'reward_valve_time'] = self.reward_time
        # update cumulative reward value
        self.session_info.TOTAL_WATER_DELIVERED += self.trials_table.at[self.trial_num, 'reward_amount']
        self.session_info.NTRIALS += 1
        # SAVE TRIAL DATA
        save_dict = self.trials_table.iloc[self.trial_num].to_dict()
        save_dict['behavior_data'] = bpod_data
        # Dump and save
        with open(self.paths['DATA_FILE_PATH'], 'a') as fp:
            fp.write(json.dumps(save_dict) + '\n')
        # this is a flag for the online plots. If online plots were in pyqt5, there is a file watcher functionality
        Path(self.paths['DATA_FILE_PATH']).parent.joinpath('new_trial.flag').touch()
        # If more than 42 trials save transfer_me.flag
        if self.trial_num == 42:
            self.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
            # todo: add number of devices in there
        self.check_sync_pulses(bpod_data=bpod_data)

    def check_sync_pulses(self, bpod_data):
        # todo move this in the post trial when we have a task flow
        if not self.bpod.is_connected:
            return
        events = bpod_data['Events timestamps']
        ev_bnc1 = misc.get_port_events(events, name='BNC1')
        ev_bnc2 = misc.get_port_events(events, name='BNC2')
        ev_port1 = misc.get_port_events(events, name='Port1')
        NOT_FOUND = 'COULD NOT FIND DATA ON {}'
        bnc1_msg = NOT_FOUND.format('BNC1') if not ev_bnc1 else 'OK'
        bnc2_msg = NOT_FOUND.format('BNC2') if not ev_bnc2 else 'OK'
        port1_msg = NOT_FOUND.format('Port1') if not ev_port1 else 'OK'
        warn_msg = f"""
            ##########################################
                    NOT FOUND: SYNC PULSES
            ##########################################
            VISUAL STIMULUS SYNC: {bnc1_msg}
            SOUND SYNC: {bnc2_msg}
            CAMERA SYNC: {port1_msg}
            ##########################################"""
        if not ev_bnc1 or not ev_bnc2 or not ev_port1:
            log.warning(warn_msg)

    def show_trial_log(self, extra_info=''):
        trial_info = self.trials_table.iloc[self.trial_num]
        msg = f"""
Session {self.paths.SESSION_RAW_DATA_FOLDER}
##########################################
TRIAL NUM:            {trial_info.trial_num}
TEMPERATURE:          {self.ambient_sensor_table.loc[self.trial_num, 'Temperature_C']} ºC
AIR PRESSURE:         {self.ambient_sensor_table.loc[self.trial_num, 'AirPressure_mb']} mb
RELATIVE HUMIDITY:    {self.ambient_sensor_table.loc[self.trial_num, 'RelativeHumidity']} %

STIM POSITION:        {trial_info.position}
STIM CONTRAST:        {trial_info.contrast}
STIM PHASE:           {trial_info.stim_phase}
STIM PROB LEFT:       {trial_info.stim_probability_left}
{extra_info}
WATER DELIVERED:      {np.round(self.session_info.TOTAL_WATER_DELIVERED, 3)} µl
TIME FROM START:      {self.time_elapsed}
##########################################"""
        log.info(msg)

    @property
    def iti_reward(self, assert_calibration=True):
        """
        Returns the ITI time that needs to be set in order to achieve the desired ITI,
        by subtracting the time it takes to give a reward from the desired ITI.
        """
        if assert_calibration:
            assert 'REWARD_VALVE_TIME' in self.calibration, 'Reward valve time not calibrated'
        return self.task_params.ITI_CORRECT - self.calibration.get('REWARD_VALVE_TIME', None)

    """
    Those are the properties that are used in the state machine code
    """

    @property
    def reward_time(self):
        return self.compute_reward_time(amount_ul=self.trials_table.at[self.trial_num, 'reward_amount'])

    @property
    def quiescent_period(self):
        return self.trials_table.at[self.trial_num, 'quiescent_period']

    @property
    def position(self):
        return self.trials_table.at[self.trial_num, 'position']

    @property
    def event_error(self):
        return self.device_rotary_encoder.THRESHOLD_EVENTS[self.position]

    @property
    def event_reward(self):
        return self.device_rotary_encoder.THRESHOLD_EVENTS[-self.position]


class HabituationChoiceWorldSession(ChoiceWorldSession):
    protocol_name = '_iblrig_tasks_habituationChoiceWorld'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trials_table['delay_to_stim_center'] = np.zeros(NTRIALS_INIT) * np.NaN

    def next_trial(self):
        self.trial_num += 1
        self.draw_next_trial_info()

    def draw_next_trial_info(self, *args, **kwargs):
        # update trial table fields specific to habituation choice world
        self.trials_table.at[self.trial_num, 'delay_to_stim_center'] = np.random.normal(self.task_params.DELAY_TO_STIM_CENTER, 2)
        super().draw_next_trial_info(*args, **kwargs)

    def get_state_machine_trial(self, i):
        sma = StateMachine(self.bpod)

        if i == 0:  # First trial exception start camera
            log.info('Waiting for camera pulses...')
            sma.add_state(
                state_name='trial_start',
                state_timer=3600,
                state_change_conditions={'Port1In': 'stim_on'},
                output_actions=[self.bpod.actions.bonsai_hide_stim, ('SoftCode', SOFTCODE.TRIGGER_CAMERA), ('BNC1', 255)],
            )  # sart camera
        else:
            sma.add_state(
                state_name='trial_start',
                state_timer=1,  # Stim off for 1 sec
                state_change_conditions={'Tup': 'stim_on'},
                output_actions=[self.bpod.actions.bonsai_hide_stim, ('BNC1', 255)],
            )

        sma.add_state(
            state_name='stim_on',
            state_timer=self.trials_table.at[self.trial_num, 'delay_to_stim_center'],
            state_change_conditions={'Tup': 'stim_center'},
            output_actions=[self.bpod.actions.bonsai_show_stim, self.bpod.actions.play_tone],
        )

        sma.add_state(
            state_name='stim_center',
            state_timer=0.5,
            state_change_conditions={'Tup': 'reward'},
            output_actions=[self.bpod.actions.bonsai_show_center],
        )

        sma.add_state(
            state_name='reward',
            state_timer=self.reward_time,
            state_change_conditions={'Tup': 'iti'},
            output_actions=[('Valve1', 255), ('BNC1', 255)],
        )

        sma.add_state(
            state_name='iti',
            state_timer=self.task_params.ITI_DELAY_SECS,
            state_change_conditions={'Tup': 'exit'},
            output_actions=[],
        )
        return sma


class ActiveChoiceWorldSession(ChoiceWorldSession):
    """
    The ActiveChoiceWorldSession is a base class for protocols where the mouse is actively making decisions
    by turning the wheel. It has the following characteristics
    -   it is trial based
    -   it is decision based
    -   left and right simulus are equiprobable: there is no biased block
    -   a trial can either be correct / error / no_go depending on the side of the stimulus and the response
    -   it has a quantifiable performance by computing the proportion of correct trials of passive stimulations protocols or
        habituation protocols.

    The TrainingChoiceWorld, BiasedChoiceWorld are all subclasses of this class
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trials_table['stim_probability_left'] = np.zeros(NTRIALS_INIT, dtype=np.float32)

    def _run(self):
        # starts online plotting
        if self.interactive:
            subprocess.Popen(
                ['viewsession', str(self.paths['DATA_FILE_PATH'])], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )
        super()._run()

    def show_trial_log(self, extra_info=''):
        trial_info = self.trials_table.iloc[self.trial_num]
        extra_info = f"""
RESPONSE TIME:        {trial_info.response_time}
{extra_info}

TRIAL CORRECT:        {trial_info.trial_correct}
NTRIALS CORRECT:      {self.session_info.NTRIALS_CORRECT}
NTRIALS ERROR:        {self.trial_num - self.session_info.NTRIALS_CORRECT}
        """
        super().show_trial_log(extra_info=extra_info)

    def trial_completed(self, bpod_data):
        """
        The purpose of this method is to
        -   update the trials table with information about the behaviour coming from the bpod
        Constraints on the state machine data:
        - mandatory states: ['correct', 'error', 'no_go', 'reward']
        - optional states : ['omit_correct', 'omit_error', 'omit_no_go']
        :param bpod_data:
        :return:
        """
        # get the response time from the behaviour data
        response_time = bpod_data['States timestamps']['closed_loop'][0][1] - bpod_data['States timestamps']['stim_on'][0][0]
        self.trials_table.at[self.trial_num, 'response_time'] = response_time
        # get the trial outcome
        state_names = ['correct', 'error', 'no_go', 'omit_correct', 'omit_error', 'omit_no_go']
        outcome = {sn: ~np.isnan(bpod_data['States timestamps'].get(sn, [[np.NaN]])[0][0]) for sn in state_names}
        assert np.sum(list(outcome.values())) == 1
        outcome = next(k for k in outcome if outcome[k])
        # Update response buffer -1 for left, 0 for nogo, and 1 for rightward
        position = self.trials_table.at[self.trial_num, 'position']
        if 'correct' in outcome:
            self.trials_table.at[self.trial_num, 'trial_correct'] = True
            self.session_info.NTRIALS_CORRECT += 1
            self.trials_table.at[self.trial_num, 'response_side'] = -np.sign(position)
        elif 'error' in outcome:
            self.trials_table.at[self.trial_num, 'response_side'] = np.sign(position)
        elif 'no_go' in outcome:
            self.trials_table.at[self.trial_num, 'response_side'] = 0
        else:
            ValueError("The task outcome doesn't contain no_go, error or correct")
        assert position != 0, 'the position value should be either 35 or -35'

        super().trial_completed(bpod_data)


class BiasedChoiceWorldSession(ActiveChoiceWorldSession):
    """
    Biased choice world session is the instantiation of ActiveChoiceWorld where the notion of biased
    blocks is introduced.
    """

    base_parameters_file = Path(__file__).parent.joinpath('base_biased_choice_world_params.yaml')
    protocol_name = '_iblrig_tasks_biasedChoiceWorld'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blocks_table = pd.DataFrame(
            {
                'probability_left': np.zeros(NBLOCKS_INIT) * np.NaN,
                'block_length': np.zeros(NBLOCKS_INIT, dtype=np.int16) * -1,
            }
        )
        self.trials_table['block_num'] = np.zeros(NTRIALS_INIT, dtype=np.int16)
        self.trials_table['block_trial_num'] = np.zeros(NTRIALS_INIT, dtype=np.int16)

    def new_block(self):
        """
        if block_init_5050
            First block has 50/50 probability of leftward stim
            is 90 trials long
        """
        self.block_num += 1  # the block number is zero based
        self.block_trial_num = 0

        # handles the block length logic
        if self.task_params.BLOCK_INIT_5050 and self.block_num == 0:
            block_len = 90
        else:
            block_len = int(
                misc.truncated_exponential(
                    scale=self.task_params.BLOCK_LEN_FACTOR,
                    min_value=self.task_params.BLOCK_LEN_MIN,
                    max_value=self.task_params.BLOCK_LEN_MAX,
                )
            )
        if self.block_num == 0:
            pleft = 0.5 if self.task_params.BLOCK_INIT_5050 else np.random.choice(self.task_params.BLOCK_PROBABILITY_SET)
        elif self.block_num == 1 and self.task_params.BLOCK_INIT_5050:
            pleft = np.random.choice(self.task_params.BLOCK_PROBABILITY_SET)
        else:
            # this switches the probability of leftward stim for the next block
            pleft = round(abs(1 - self.blocks_table.loc[self.block_num - 1, 'probability_left']), 1)
        self.blocks_table.at[self.block_num, 'block_length'] = block_len
        self.blocks_table.at[self.block_num, 'probability_left'] = pleft

    def next_trial(self):
        self.trial_num += 1
        # if necessary update the block number
        self.block_trial_num += 1
        if self.block_num < 0 or self.block_trial_num > (self.blocks_table.loc[self.block_num, 'block_length'] - 1):
            self.new_block()
        # get and store probability left
        pleft = self.blocks_table.loc[self.block_num, 'probability_left']
        # update trial table fields specific to biased choice world task
        self.trials_table.at[self.trial_num, 'block_num'] = self.block_num
        self.trials_table.at[self.trial_num, 'block_trial_num'] = self.block_trial_num
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=pleft)

    def show_trial_log(self):
        trial_info = self.trials_table.iloc[self.trial_num]
        extra_info = f"""
BLOCK NUMBER:         {trial_info.block_num}
BLOCK LENGTH:         {self.blocks_table.loc[self.block_num, 'block_length']}
TRIALS IN BLOCK:      {trial_info.block_trial_num}
        """
        super().show_trial_log(extra_info=extra_info)


class TrainingChoiceWorldSession(ActiveChoiceWorldSession):
    """
    The TrainingChoiceWorldSession corresponds to the first training protocol of the choice world task.
    This protocol has a complicated adaptation of the number of contrasts (embodied by the training_phase
    property) and the reward amount, embodied by the adaptive_reward property.
    """

    protocol_name = '_iblrig_tasks_trainingChoiceWorld'

    def __init__(self, training_phase=-1, adaptive_reward=-1.0, adaptive_gain=None, **kwargs):
        super().__init__(**kwargs)
        inferred_training_phase, inferred_adaptive_reward, inferred_adaptive_gain = self.get_subject_training_info()
        if training_phase == -1:
            self.logger.critical(f'Got training phase: {inferred_training_phase}')
            self.training_phase = inferred_training_phase
        else:
            self.logger.critical(f'Training phase manually set to: {training_phase}')
            self.training_phase = training_phase
        if adaptive_reward == -1:
            self.logger.critical(f'Got Adaptive reward {inferred_adaptive_reward} uL')
            self.session_info['ADAPTIVE_REWARD_AMOUNT_UL'] = inferred_adaptive_reward
        else:
            self.logger.critical(f'Adaptive reward manually set to {adaptive_reward} uL')
            self.session_info['ADAPTIVE_REWARD_AMOUNT_UL'] = adaptive_reward
        if adaptive_gain is None:
            self.logger.critical(f'Got Adaptive gain {inferred_adaptive_gain} degrees/mm')
            self.session_info['ADAPTIVE_GAIN_VALUE'] = inferred_adaptive_gain
        else:
            self.logger.critical(f'Adaptive gain manually set to {adaptive_gain} degrees/mm')
            self.session_info['ADAPTIVE_GAIN_VALUE'] = adaptive_gain
        self.var = {
            'training_phase_trial_counts': np.zeros(6),
            'last_10_responses_sides': np.zeros(10),
        }
        self.trials_table['training_phase'] = np.zeros(NTRIALS_INIT, dtype=np.int8)
        self.trials_table['debias_trial'] = np.zeros(NTRIALS_INIT, dtype=bool)

    @property
    def reward_amount(self):
        return self.session_info.get('ADAPTIVE_REWARD_AMOUNT_UL', self.task_params.REWARD_AMOUNT_UL)

    def get_subject_training_info(self):
        """
        Get the previous session's according to this session parameters and deduce the
        training level, adaptive reward amount and adaptive gain value
        :return:
        """
        try:
            tinfo, _ = choiceworld.get_subject_training_info(
                subject_name=self.session_info.SUBJECT_NAME,
                default_reward=self.task_params.REWARD_AMOUNT_UL,
                stim_gain=self.task_params.STIM_GAIN,
                local_path=self.iblrig_settings['iblrig_local_data_path'],
                remote_path=self.iblrig_settings['iblrig_remote_data_path'],
                lab=self.iblrig_settings['ALYX_LAB'],
                task_name=self.protocol_name,
            )
        except Exception:
            self.logger.critical('Failed to get training information from previous subjects: %s', traceback.format_exc())
            tinfo = dict(
                training_phase=iblrig.choiceworld.DEFAULT_TRAINING_PHASE,
                adaptive_reward=iblrig.choiceworld.DEFAULT_REWARD_VOLUME,
                adaptive_gain=self.task_params.AG_INIT_VALUE,
            )
            self.logger.critical(
                f"The mouse will train on level {tinfo['training_phase']}, "
                f"with reward {tinfo['adaptive_reward']} uL and gain {tinfo['adaptive_gain']}"
            )
        return tinfo['training_phase'], tinfo['adaptive_reward'], tinfo['adaptive_gain']

    def compute_performance(self):
        """
        Aggregates the trials table to compute the performance of the mouse on each contrast
        :return: None
        """
        self.trials_table['signed_contrast'] = self.trials_table['contrast'] * np.sign(self.trials_table['position'])
        performance = self.trials_table.groupby(['signed_contrast']).agg(
            last_50_perf=pd.NamedAgg(column='trial_correct', aggfunc=lambda x: np.sum(x[np.maximum(-50, -x.size) :]) / 50),
            ntrials=pd.NamedAgg(column='trial_correct', aggfunc='count'),
        )
        return performance

    def check_training_phase(self):
        """
        Checks if the mouse is ready to move to the next training phase
        :return: None
        """
        move_on = False
        if self.training_phase == 0:  # each of the -1, -.5, .5, 1 contrast should be above 80% perf to switch
            performance = self.compute_performance()
            passing = performance[np.abs(performance.index) >= 0.5]['last_50_perf']
            if np.all(passing > 0.8) and passing.size == 4:
                move_on = True
        elif self.training_phase == 1:  # each of the -.25, .25 should be above 80% perf to switch
            performance = self.compute_performance()
            passing = performance[np.abs(performance.index) == 0.25]['last_50_perf']
            if np.all(passing > 0.8) and passing.size == 2:
                move_on = True
        elif 5 > self.training_phase >= 2:  # for the next phases, always switch after 200 trials
            if self.var['training_phase_trial_counts'][self.training_phase] >= 200:
                move_on = True
        if move_on:
            self.training_phase = np.minimum(5, self.training_phase + 1)
            log.warning(f'Moving on to training phase {self.training_phase}, {self.trial_num}')

    def next_trial(self):
        # update counters
        self.trial_num += 1
        self.var['training_phase_trial_counts'][self.training_phase] += 1
        # check if the subject graduates to a new training phase
        self.check_training_phase()
        # draw the next trial
        signed_contrast = choiceworld.draw_training_contrast(self.training_phase)
        position = self.task_params.STIM_POSITIONS[int(np.sign(signed_contrast) == 1)]
        contrast = np.abs(signed_contrast)
        # debiasing: if the previous trial was incorrect and easy repeat the trial
        if self.task_params.DEBIAS and self.trial_num >= 1 and self.training_phase < 5:
            last_contrast = self.trials_table.loc[self.trial_num - 1, 'contrast']
            do_debias_trial = (self.trials_table.loc[self.trial_num - 1, 'trial_correct'] != 1) and last_contrast >= 0.5
            self.trials_table.at[self.trial_num, 'debias_trial'] = do_debias_trial
            if do_debias_trial:
                iresponse = self.trials_table['response_side'] != 0  # trials that had a response
                # takes the average of right responses over last 10 response trials
                average_right = np.mean(self.trials_table['response_side'][iresponse[-np.maximum(10, iresponse.size) :]] == 1)
                # the next probability of next stimulus being on the left is a draw from a normal distribution
                # centered on average right with sigma 0.5. If it is less than 0.5 the next stimulus will be on the left
                position = self.task_params.STIM_POSITIONS[int(np.random.normal(average_right, 0.5) >= 0.5)]
                # contrast is the last contrast
                contrast = last_contrast
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=self.task_params.PROBABILITY_LEFT, position=position, contrast=contrast)
        self.trials_table.at[self.trial_num, 'training_phase'] = self.training_phase

    def show_trial_log(self):
        extra_info = f"""
CONTRAST SET:         {np.unique(np.abs(choiceworld.contrasts_set(self.training_phase)))}
SUBJECT TRAINING PHASE (0-5):         {self.training_phase}
            """
        super().show_trial_log(extra_info=extra_info)
