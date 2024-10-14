"""Extends the base_tasks modules by providing task logic around the Choice World protocol."""

import abc
import logging
import math
import random
import subprocess
import time
from pathlib import Path
from string import ascii_letters
from typing import Annotated, Any

import numpy as np
import pandas as pd
from annotated_types import Interval, IsNan
from pydantic import NonNegativeFloat, NonNegativeInt, create_model, Field
from pydantic_settings import BaseSettings

import iblrig.base_tasks
import iblrig.graphic
from iblrig import choiceworld, misc
from iblrig.hardware import SOFTCODE
from iblrig.pydantic_definitions import TrialDataModel
from iblutil.io import jsonable
from iblutil.util import Bunch
from pybpodapi.com.messaging.trial import Trial
from pybpodapi.protocol import StateMachine

log = logging.getLogger(__name__)

NTRIALS_INIT = 2000
NBLOCKS_INIT = 100

# TODO: task parameters should be verified through a pydantic model
#
# Probability = Annotated[float, Field(ge=0.0, le=1.0)]
#
# class ChoiceWorldParams(BaseModel):
#     AUTOMATIC_CALIBRATION: bool = True
#     ADAPTIVE_REWARD: bool = False
#     BONSAI_EDITOR: bool = False
#     CALIBRATION_VALUE: float = 0.067
#     CONTRAST_SET: list[Probability] = Field([1.0, 0.25, 0.125, 0.0625, 0.0], min_length=1)
#     CONTRAST_SET_PROBABILITY_TYPE: Literal['uniform', 'skew_zero'] = 'uniform'
#     GO_TONE_AMPLITUDE: float = 0.0272
#     GO_TONE_DURATION: float = 0.11
#     GO_TONE_IDX: int = Field(2, ge=0)
#     GO_TONE_FREQUENCY: float = Field(5000, gt=0)
#     FEEDBACK_CORRECT_DELAY_SECS: float = 1
#     FEEDBACK_ERROR_DELAY_SECS: float = 2
#     FEEDBACK_NOGO_DELAY_SECS: float = 2
#     INTERACTIVE_DELAY: float = 0.0
#     ITI_DELAY_SECS: float = 0.5
#     NTRIALS: int = Field(2000, gt=0)
#     PROBABILITY_LEFT: Probability = 0.5
#     QUIESCENCE_THRESHOLDS: list[float] = Field(default=[-2, 2], min_length=2, max_length=2)
#     QUIESCENT_PERIOD: float = 0.2
#     RECORD_AMBIENT_SENSOR_DATA: bool = True
#     RECORD_SOUND: bool = True
#     RESPONSE_WINDOW: float = 60
#     REWARD_AMOUNT_UL: float = 1.5
#     REWARD_TYPE: str = 'Water 10% Sucrose'
#     STIM_ANGLE: float = 0.0
#     STIM_FREQ: float = 0.1
#     STIM_GAIN: float = 4.0  # wheel to stimulus relationship (degrees visual angle per mm of wheel displacement)
#     STIM_POSITIONS: list[float] = [-35, 35]
#     STIM_SIGMA: float = 7.0
#     STIM_TRANSLATION_Z: Literal[7, 8] = 7  # 7 for ephys, 8 otherwise. -p:Stim.TranslationZ-{STIM_TRANSLATION_Z} bonsai param
#     STIM_REVERSE: bool = False
#     SYNC_SQUARE_X: float = 1.33
#     SYNC_SQUARE_Y: float = -1.03
#     USE_AUTOMATIC_STOPPING_CRITERIONS: bool = True
#     VISUAL_STIMULUS: str = 'GaborIBLTask / Gabor2D.bonsai'  # null / passiveChoiceWorld_passive.bonsai
#     WHITE_NOISE_AMPLITUDE: float = 0.05
#     WHITE_NOISE_DURATION: float = 0.5
#     WHITE_NOISE_IDX: int = 3


class ChoiceWorldTrialData(TrialDataModel):
    """Pydantic Model for Trial Data."""

    contrast: Annotated[float, Interval(ge=0.0, le=1.0)]
    stim_probability_left: Annotated[float, Interval(ge=0.0, le=1.0)]
    position: float
    quiescent_period: NonNegativeFloat
    reward_amount: NonNegativeFloat
    reward_valve_time: NonNegativeFloat
    stim_angle: Annotated[float, Interval(ge=-180.0, le=180.0)]
    stim_freq: NonNegativeFloat
    stim_gain: float
    stim_phase: Annotated[float, Interval(ge=0.0, le=2 * math.pi)]
    stim_reverse: bool
    stim_sigma: float
    trial_num: NonNegativeInt
    pause_duration: NonNegativeFloat = 0.0

    # The following variables are only used in ActiveChoiceWorld
    # We keep them here with fixed default values for sake of compatibility
    #
    # TODO: Yes, this should probably be done differently.
    response_side: Annotated[int, Interval(ge=0, le=0)] = 0
    response_time: IsNan[float] = np.nan
    trial_correct: Annotated[bool, Interval(ge=0, le=0)] = False


class ChoiceWorldSession(
    iblrig.base_tasks.BonsaiRecordingMixin,
    iblrig.base_tasks.BonsaiVisualStimulusMixin,
    iblrig.base_tasks.BpodMixin,
    iblrig.base_tasks.Frame2TTLMixin,
    iblrig.base_tasks.RotaryEncoderMixin,
    iblrig.base_tasks.SoundMixin,
    iblrig.base_tasks.ValveMixin,
    iblrig.base_tasks.NetworkSession,
):
    # task_params = ChoiceWorldParams()
    base_parameters_file = Path(__file__).parent.joinpath('base_choice_world_params.yaml')
    TrialDataModel = ChoiceWorldTrialData

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
        self.trials_table = self.TrialDataModel.preallocate_dataframe(NTRIALS_INIT)
        self.ambient_sensor_table = pd.DataFrame(
            {
                'Temperature_C': np.zeros(NTRIALS_INIT) * np.nan,
                'AirPressure_mb': np.zeros(NTRIALS_INIT) * np.nan,
                'RelativeHumidity': np.zeros(NTRIALS_INIT) * np.nan,
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
        parser.add_argument(
            '--remote',
            dest='remote_rigs',
            type=str,
            required=False,
            action='append',
            nargs='+',
            help='specify one of the remote rigs to interact with over the network',
        )
        return parser

    @staticmethod
    def get_settings_model() -> type[BaseSettings]:
        SuperSettings = super(ChoiceWorldSession, ChoiceWorldSession).get_settings_model()
        return create_model(
            SuperSettings.__name__,
            delay_secs=(int, Field(description='initial delay before starting the first trial', default=0)),
            remote_rigs=(
                list[str] | None,
                Field(description='remote rigs to interact with over the network', default=None),
            ),
            __base__=SuperSettings,
        )

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
            self.bpod.register_softcodes(self.softcode_dictionary())

    def _run(self):
        """Run the task with the actual state machine."""
        time_last_trial_end = time.time()
        for i in range(self.task_params.NTRIALS):  # Main loop
            # t_overhead = time.time()
            self.next_trial()
            log.info(f'Starting trial: {i}')
            # =============================================================================
            #     Start state machine definition
            # =============================================================================
            sma = self.get_state_machine_trial(i)
            log.debug('Sending state machine to bpod')
            # Send state machine description to Bpod device
            self.bpod.send_state_machine(sma)
            # t_overhead = time.time() - t_overhead
            # The ITI_DELAY_SECS defines the grey screen period within the state machine, where the
            # Bpod TTL is HIGH. The DEAD_TIME param defines the time between last trial and the next
            dead_time = self.task_params.get('DEAD_TIME', 0.5)
            dt = self.task_params.ITI_DELAY_SECS - dead_time - (time.time() - time_last_trial_end)
            # wait to achieve the desired ITI duration
            if dt > 0:
                time.sleep(dt)
            # Run state machine
            log.debug('running state machine')
            self.bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
            time_last_trial_end = time.time()
            # handle pause event
            flag_pause = self.paths.SESSION_FOLDER.joinpath('.pause')
            flag_stop = self.paths.SESSION_FOLDER.joinpath('.stop')
            if flag_pause.exists() and i < (self.task_params.NTRIALS - 1):
                log.info(f'Pausing session inbetween trials {i} and {i + 1}')
                while flag_pause.exists() and not flag_stop.exists():
                    time.sleep(1)
                self.trials_table.at[self.trial_num, 'pause_duration'] = time.time() - time_last_trial_end
                if not flag_stop.exists():
                    log.info('Resuming session')

            # save trial and update log
            self.trial_completed(self.bpod.session.current_trial.export())
            self.ambient_sensor_table.loc[i] = self.bpod.get_ambient_sensor_reading()
            self.show_trial_log()

            # handle stop event
            if flag_stop.exists():
                log.info('Stopping session after trial %d', i)
                flag_stop.unlink()
                break

    def mock(self, file_jsonable_fixture=None):
        """
        Instantiate a state machine and Bpod object to simulate a task's run.

        This is useful to test or display the state machine flow.
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
        self.sound = Bunch({'GO_TONE': daction, 'WHITE_NOISE': daction})

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
        Get the state machine's states diagram in Digraph format.

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

    def _instantiate_state_machine(self, *args, **kwargs):
        return StateMachine(self.bpod)

    def get_state_machine_trial(self, i):
        # we define the trial number here for subclasses that may need it
        sma = self._instantiate_state_machine(trial_number=i)

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

        # Reset the rotary encoder by sending the following opcodes via the modules serial interface
        # - 'Z' (ASCII 90): Set current rotary encoder position to zero
        # - 'E' (ASCII 69): Enable all position thresholds (that may have been disabled by a threshold-crossing)
        # cf. https://sanworks.github.io/Bpod_Wiki/serial-interfaces/rotary-encoder-module-serial-interface/
        sma.add_state(
            state_name='reset_rotary_encoder',
            state_timer=0,
            output_actions=[self.bpod.actions.rotary_encoder_reset],
            state_change_conditions={'Tup': 'quiescent_period'},
        )

        # Quiescent Period. If the wheel is moved past one of the thresholds: Reset the rotary encoder and start over.
        # Continue with the stimulation once the quiescent period has passed without triggering movement thresholds.
        sma.add_state(
            state_name='quiescent_period',
            state_timer=self.quiescent_period,
            output_actions=[],
            state_change_conditions={
                'Tup': 'stim_on',
                self.movement_left: 'reset_rotary_encoder',
                self.movement_right: 'reset_rotary_encoder',
            },
        )

        # Show the visual stimulus. This is achieved by sending a time-stamped byte-message to Bonsai via the Rotary
        # Encoder Module's ongoing USB-stream. Move to the next state once the Frame2TTL has been triggered, i.e.,
        # when the stimulus has been rendered on screen. Use the state-timer as a backup to prevent a stall.
        sma.add_state(
            state_name='stim_on',
            state_timer=0.1,
            output_actions=[self.bpod.actions.bonsai_show_stim],
            state_change_conditions={'BNC1High': 'interactive_delay', 'BNC1Low': 'interactive_delay', 'Tup': 'interactive_delay'},
        )

        # Defined delay between visual and auditory cue
        sma.add_state(
            state_name='interactive_delay',
            state_timer=self.task_params.INTERACTIVE_DELAY,
            output_actions=[],
            state_change_conditions={'Tup': 'play_tone'},
        )

        # Play tone. Move to next state if sound is detected. Use the state-timer as a backup to prevent a stall.
        sma.add_state(
            state_name='play_tone',
            state_timer=0.1,
            output_actions=[self.bpod.actions.play_tone],
            state_change_conditions={'Tup': 'reset2_rotary_encoder', 'BNC2High': 'reset2_rotary_encoder'},
        )

        # Reset rotary encoder (see above). Move on after brief delay (to avoid a race conditions in the bonsai flow).
        sma.add_state(
            state_name='reset2_rotary_encoder',
            state_timer=0.05,
            output_actions=[self.bpod.actions.rotary_encoder_reset],
            state_change_conditions={'Tup': 'closed_loop'},
        )

        # Start the closed loop state in which the animal controls the position of the visual stimulus by means of the
        # rotary encoder. The three possible outcomes are:
        # 1) wheel has NOT been moved past a threshold: continue with no-go condition
        # 2) wheel has been moved in WRONG direction: continue with error condition
        # 3) wheel has been moved in CORRECT direction: continue with reward condition

        sma.add_state(
            state_name='closed_loop',
            state_timer=self.task_params.RESPONSE_WINDOW,
            output_actions=[self.bpod.actions.bonsai_closed_loop],
            state_change_conditions={'Tup': 'no_go', self.event_error: 'freeze_error', self.event_reward: 'freeze_reward'},
        )

        # No-go: hide the visual stimulus and play white noise. Go to exit_state after FEEDBACK_NOGO_DELAY_SECS.
        sma.add_state(
            state_name='no_go',
            state_timer=self.task_params.FEEDBACK_NOGO_DELAY_SECS,
            output_actions=[self.bpod.actions.bonsai_hide_stim, self.bpod.actions.play_noise],
            state_change_conditions={'Tup': 'exit_state'},
        )

        # Error: Freeze the stimulus and play white noise.
        # Continue to hide_stim/exit_state once FEEDBACK_ERROR_DELAY_SECS have passed.
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

        # Reward: open the valve for a defined duration (and set BNC1 to high), freeze stimulus in center of screen.
        # Continue to hide_stim/exit_state once FEEDBACK_CORRECT_DELAY_SECS have passed.
        sma.add_state(
            state_name='freeze_reward',
            state_timer=0,
            output_actions=[self.bpod.actions.bonsai_show_center],
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
            state_timer=self.task_params.FEEDBACK_CORRECT_DELAY_SECS - self.reward_time,
            output_actions=[],
            state_change_conditions={'Tup': 'hide_stim'},
        )

        # Hide the visual stimulus. This is achieved by sending a time-stamped byte-message to Bonsai via the Rotary
        # Encoder Module's ongoing USB-stream. Move to the next state once the Frame2TTL has been triggered, i.e.,
        # when the stimulus has been rendered on screen. Use the state-timer as a backup to prevent a stall.
        sma.add_state(
            state_name='hide_stim',
            state_timer=0.1,
            output_actions=[self.bpod.actions.bonsai_hide_stim],
            state_change_conditions={'Tup': 'exit_state', 'BNC1High': 'exit_state', 'BNC1Low': 'exit_state'},
        )

        # Wait for ITI_DELAY_SECS before ending the trial. Raise BNC1 to mark this event.
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
    def default_reward_amount(self):
        return self.task_params.REWARD_AMOUNT_UL

    def draw_next_trial_info(self, pleft=0.5, **kwargs):
        """Draw next trial variables.

        calls :meth:`send_trial_info_to_bonsai`.
        This is called by the `next_trial` method before updating the Bpod state machine.
        """
        assert len(self.task_params.STIM_POSITIONS) == 2, 'Only two positions are supported'
        contrast = misc.draw_contrast(self.task_params.CONTRAST_SET, self.task_params.CONTRAST_SET_PROBABILITY_TYPE)
        position = int(np.random.choice(self.task_params.STIM_POSITIONS, p=[pleft, 1 - pleft]))
        quiescent_period = self.task_params.QUIESCENT_PERIOD + misc.truncated_exponential(
            scale=0.35, min_value=0.2, max_value=0.5
        )
        stim_gain = (
            self.session_info.ADAPTIVE_GAIN_VALUE if self.task_params.get('ADAPTIVE_GAIN', False) else self.task_params.STIM_GAIN
        )
        self.trials_table.at[self.trial_num, 'quiescent_period'] = quiescent_period
        self.trials_table.at[self.trial_num, 'contrast'] = contrast
        self.trials_table.at[self.trial_num, 'stim_phase'] = random.uniform(0, 2 * math.pi)
        self.trials_table.at[self.trial_num, 'stim_sigma'] = self.task_params.STIM_SIGMA
        self.trials_table.at[self.trial_num, 'stim_angle'] = self.task_params.STIM_ANGLE
        self.trials_table.at[self.trial_num, 'stim_gain'] = stim_gain
        self.trials_table.at[self.trial_num, 'stim_freq'] = self.task_params.STIM_FREQ
        self.trials_table.at[self.trial_num, 'stim_reverse'] = self.task_params.STIM_REVERSE
        self.trials_table.at[self.trial_num, 'trial_num'] = self.trial_num
        self.trials_table.at[self.trial_num, 'position'] = position
        self.trials_table.at[self.trial_num, 'reward_amount'] = self.default_reward_amount
        self.trials_table.at[self.trial_num, 'stim_probability_left'] = pleft

        # use the kwargs dict to override computed values
        for key, value in kwargs.items():
            if key == 'index':
                pass
            self.trials_table.at[self.trial_num, key] = value

        self.send_trial_info_to_bonsai()

    def trial_completed(self, bpod_data: dict[str, Any]) -> None:
        # if the reward state has not been triggered, null the reward
        if np.isnan(bpod_data['States timestamps']['reward'][0][0]):
            self.trials_table.at[self.trial_num, 'reward_amount'] = 0
        self.trials_table.at[self.trial_num, 'reward_valve_time'] = self.reward_time
        # update cumulative reward value
        self.session_info.TOTAL_WATER_DELIVERED += self.trials_table.at[self.trial_num, 'reward_amount']
        self.session_info.NTRIALS += 1
        # SAVE TRIAL DATA
        self.save_trial_data_to_json(bpod_data)
        # this is a flag for the online plots. If online plots were in pyqt5, there is a file watcher functionality
        Path(self.paths['DATA_FILE_PATH']).parent.joinpath('new_trial.flag').touch()
        self.paths.SESSION_FOLDER.joinpath('transfer_me.flag').touch()
        self.check_sync_pulses(bpod_data=bpod_data)

    def check_sync_pulses(self, bpod_data):
        # todo move this in the post trial when we have a task flow
        if not self.bpod.is_connected:
            return
        events = bpod_data['Events timestamps']
        if not misc.get_port_events(events, name='BNC1'):
            log.warning("NO FRAME2TTL PULSES RECEIVED ON BPOD'S TTL INPUT 1")
        if not misc.get_port_events(events, name='BNC2'):
            log.warning("NO SOUND SYNC PULSES RECEIVED ON BPOD'S TTL INPUT 2")
        if not misc.get_port_events(events, name='Port1'):
            log.warning("NO CAMERA SYNC PULSES RECEIVED ON BPOD'S BEHAVIOR PORT 1")

    def show_trial_log(self, extra_info: dict[str, Any] | None = None, log_level: int = logging.INFO):
        """
        Log the details of the current trial.

        This method retrieves information about the current trial from the
        trials table and logs it. It can also incorporate additional information
        provided through the `extra_info` parameter.

        Parameters
        ----------
        extra_info : dict[str, Any], optional
            A dictionary containing additional information to include in the
            log.

        log_level : int, optional
            The logging level to use when logging the trial information.
            Default is logging.INFO.

        Notes
        -----
        When overloading, make sure to call the super class and pass additional
        log items by means of the extra_info parameter. See the implementation
        of :py:meth:`~iblrig.base_choice_world.ActiveChoiceWorldSession.show_trial_log` in
        :mod:`~iblrig.base_choice_world.ActiveChoiceWorldSession` for reference.
        """
        # construct base info dict
        trial_info = self.trials_table.iloc[self.trial_num]
        info_dict = {
            'Stim. Position': trial_info.position,
            'Stim. Contrast': trial_info.contrast,
            'Stim. Phase': f'{trial_info.stim_phase:.2f}',
            'Stim. p Left': trial_info.stim_probability_left,
            'Water delivered': f'{self.session_info.TOTAL_WATER_DELIVERED:.1f} µl',
            'Time from Start': self.time_elapsed,
            'Temperature': f'{self.ambient_sensor_table.loc[self.trial_num, "Temperature_C"]:.1f} °C',
            'Air Pressure': f'{self.ambient_sensor_table.loc[self.trial_num, "AirPressure_mb"]:.1f} mb',
            'Rel. Humidity': f'{self.ambient_sensor_table.loc[self.trial_num, "RelativeHumidity"]:.1f} %',
        }

        # update info dict with extra_info dict
        if isinstance(extra_info, dict):
            info_dict.update(extra_info)

        # log info dict
        log.log(log_level, f'Outcome of Trial #{trial_info.trial_num}:')
        max_key_length = max(len(key) for key in info_dict)
        for key, value in info_dict.items():
            spaces = (max_key_length - len(key)) * ' '
            log.log(log_level, f'- {key}: {spaces}{str(value)}')

    @property
    def iti_reward(self):
        """
        Returns the ITI time that needs to be set in order to achieve the desired ITI,
        by subtracting the time it takes to give a reward from the desired ITI.
        """
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
        return self.device_rotary_encoder.THRESHOLD_EVENTS[(-1 if self.task_params.STIM_REVERSE else 1) * self.position]

    @property
    def event_reward(self):
        return self.device_rotary_encoder.THRESHOLD_EVENTS[(1 if self.task_params.STIM_REVERSE else -1) * self.position]


class HabituationChoiceWorldTrialData(ChoiceWorldTrialData):
    """Pydantic Model for Trial Data, extended from :class:`~.iblrig.base_choice_world.ChoiceWorldTrialData`."""

    delay_to_stim_center: NonNegativeFloat


class HabituationChoiceWorldSession(ChoiceWorldSession):
    protocol_name = '_iblrig_tasks_habituationChoiceWorld'
    TrialDataModel = HabituationChoiceWorldTrialData

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
                state_name='iti',
                state_timer=3600,
                state_change_conditions={'Port1In': 'stim_on'},
                output_actions=[self.bpod.actions.bonsai_hide_stim, ('SoftCode', SOFTCODE.TRIGGER_CAMERA), ('BNC1', 255)],
            )  # start camera
        else:
            # NB: This state actually the inter-trial interval, i.e. the period of grey screen between stim off and stim on.
            # During this period the Bpod TTL is HIGH and there are no stimuli. The onset of this state is trial end;
            # the offset of this state is trial start!
            sma.add_state(
                state_name='iti',
                state_timer=1,  # Stim off for 1 sec
                state_change_conditions={'Tup': 'stim_on'},
                output_actions=[self.bpod.actions.bonsai_hide_stim, ('BNC1', 255)],
            )
        # This stim_on state is considered the actual trial start
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
            state_timer=self.reward_time,  # the length of time to leave reward valve open, i.e. reward size
            state_change_conditions={'Tup': 'post_reward'},
            output_actions=[('Valve1', 255), ('BNC1', 255)],
        )
        # This state defines the period after reward where Bpod TTL is LOW.
        # NB: The stimulus is on throughout this period. The stim off trigger occurs upon exit.
        # The stimulus thus remains in the screen centre for 0.5 + ITI_DELAY_SECS seconds.
        sma.add_state(
            state_name='post_reward',
            state_timer=self.task_params.ITI_DELAY_SECS - self.reward_time,
            state_change_conditions={'Tup': 'exit'},
            output_actions=[],
        )
        return sma


class ActiveChoiceWorldTrialData(ChoiceWorldTrialData):
    """Pydantic Model for Trial Data, extended from :class:`~.iblrig.base_choice_world.ChoiceWorldTrialData`."""

    response_side: Annotated[int, Interval(ge=-1, le=1)]
    response_time: NonNegativeFloat
    trial_correct: bool


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

    TrialDataModel = ActiveChoiceWorldTrialData

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trials_table['stim_probability_left'] = np.zeros(NTRIALS_INIT, dtype=np.float64)

    def _run(self):
        # starts online plotting
        if self.interactive:
            subprocess.Popen(
                ['view_session', str(self.paths['DATA_FILE_PATH']), str(self.paths['SETTINGS_FILE_PATH'])],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
        super()._run()

    def show_trial_log(self, extra_info: dict[str, Any] | None = None, log_level: int = logging.INFO):
        # construct info dict
        trial_info = self.trials_table.iloc[self.trial_num]
        info_dict = {
            'Response Time': f'{trial_info.response_time:.2f} s',
            'Trial Correct': trial_info.trial_correct,
            'N Trials Correct': self.session_info.NTRIALS_CORRECT,
            'N Trials Error': self.trial_num - self.session_info.NTRIALS_CORRECT,
        }

        # update info dict with extra_info dict
        if isinstance(extra_info, dict):
            info_dict.update(extra_info)

        # call parent method
        super().show_trial_log(extra_info=info_dict, log_level=log_level)

    def trial_completed(self, bpod_data):
        """
        The purpose of this method is to

        - update the trials table with information about the behaviour coming from the bpod
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
        raw_outcome = {sn: ~np.isnan(bpod_data['States timestamps'].get(sn, [[np.nan]])[0][0]) for sn in state_names}
        try:
            outcome = next(k for k in raw_outcome if raw_outcome[k])
            # Update response buffer -1 for left, 0 for nogo, and 1 for rightward
            position = self.trials_table.at[self.trial_num, 'position']
            self.trials_table.at[self.trial_num, 'trial_correct'] = 'correct' in outcome
            if 'correct' in outcome:
                self.session_info.NTRIALS_CORRECT += 1
                self.trials_table.at[self.trial_num, 'response_side'] = -np.sign(position)
            elif 'error' in outcome:
                self.trials_table.at[self.trial_num, 'response_side'] = np.sign(position)
            elif 'no_go' in outcome:
                self.trials_table.at[self.trial_num, 'response_side'] = 0
            super().trial_completed(bpod_data)
            # here we throw potential errors after having written the trial to disk
            assert np.sum(list(raw_outcome.values())) == 1
            assert position != 0, 'the position value should be either 35 or -35'
        except StopIteration as e:
            log.error(f'No outcome detected for trial {self.trial_num}.')
            log.error(f'raw_outcome: {raw_outcome}')
            log.error('State names: ' + ', '.join(bpod_data['States timestamps'].keys()))
            raise e
        except AssertionError as e:
            log.error(f'Assertion Error in trial {self.trial_num}.')
            log.error(f'raw_outcome: {raw_outcome}')
            log.error('State names: ' + ', '.join(bpod_data['States timestamps'].keys()))
            raise e


class BiasedChoiceWorldTrialData(ActiveChoiceWorldTrialData):
    """Pydantic Model for Trial Data, extended from :class:`~.iblrig.base_choice_world.ChoiceWorldTrialData`."""

    block_num: NonNegativeInt = 0
    block_trial_num: NonNegativeInt = 0


class BiasedChoiceWorldSession(ActiveChoiceWorldSession):
    """
    Biased choice world session is the instantiation of ActiveChoiceWorld where the notion of biased
    blocks is introduced.
    """

    base_parameters_file = Path(__file__).parent.joinpath('base_biased_choice_world_params.yaml')
    protocol_name = '_iblrig_tasks_biasedChoiceWorld'
    TrialDataModel = BiasedChoiceWorldTrialData

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blocks_table = pd.DataFrame(
            {'probability_left': np.zeros(NBLOCKS_INIT) * np.nan, 'block_length': np.zeros(NBLOCKS_INIT, dtype=np.int16) * -1}
        )

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

    def show_trial_log(self, extra_info: dict[str, Any] | None = None, log_level: int = logging.INFO):
        # construct info dict
        trial_info = self.trials_table.iloc[self.trial_num]
        info_dict = {
            'Block Number': trial_info.block_num,
            'Block Length': self.blocks_table.loc[self.block_num, 'block_length'],
            'N Trials in Block': trial_info.block_trial_num,
        }

        # update info dict with extra_info dict
        if isinstance(extra_info, dict):
            info_dict.update(extra_info)

        # call parent method
        super().show_trial_log(extra_info=info_dict, log_level=log_level)


class TrainingChoiceWorldTrialData(ActiveChoiceWorldTrialData):
    """Pydantic Model for Trial Data, extended from :class:`~.iblrig.base_choice_world.ActiveChoiceWorldTrialData`."""

    training_phase: NonNegativeInt
    debias_trial: bool
    signed_contrast: float | None = None


class TrainingChoiceWorldSession(ActiveChoiceWorldSession):
    """
    The TrainingChoiceWorldSession corresponds to the first training protocol of the choice world task.
    This protocol has a complicated adaptation of the number of contrasts (embodied by the training_phase
    property) and the reward amount, embodied by the adaptive_reward property.
    """

    protocol_name = '_iblrig_tasks_trainingChoiceWorld'
    TrialDataModel = TrainingChoiceWorldTrialData

    def __init__(self, training_phase=-1, adaptive_reward=-1.0, adaptive_gain=None, **kwargs):
        super().__init__(**kwargs)
        inferred_training_phase, inferred_adaptive_reward, inferred_adaptive_gain = self.get_subject_training_info()
        if training_phase == -1:
            log.critical(f'Got training phase: {inferred_training_phase}')
            self.training_phase = inferred_training_phase
        else:
            log.critical(f'Training phase manually set to: {training_phase}')
            self.training_phase = training_phase
        if adaptive_reward == -1:
            log.critical(f'Got Adaptive reward {inferred_adaptive_reward} uL')
            self.session_info['ADAPTIVE_REWARD_AMOUNT_UL'] = inferred_adaptive_reward
        else:
            log.critical(f'Adaptive reward manually set to {adaptive_reward} uL')
            self.session_info['ADAPTIVE_REWARD_AMOUNT_UL'] = adaptive_reward
        if adaptive_gain is None:
            log.critical(f'Got Adaptive gain {inferred_adaptive_gain} degrees/mm')
            self.session_info['ADAPTIVE_GAIN_VALUE'] = inferred_adaptive_gain
        else:
            log.critical(f'Adaptive gain manually set to {adaptive_gain} degrees/mm')
            self.session_info['ADAPTIVE_GAIN_VALUE'] = adaptive_gain
        self.var = {'training_phase_trial_counts': np.zeros(6), 'last_10_responses_sides': np.zeros(10)}

    @property
    def default_reward_amount(self):
        return self.session_info.get('ADAPTIVE_REWARD_AMOUNT_UL', self.task_params.REWARD_AMOUNT_UL)

    def get_subject_training_info(self):
        """
        Get the previous session's according to this session parameters and deduce the
        training level, adaptive reward amount and adaptive gain value.

        Returns
        -------
        training_info: dict
            Dictionary with keys: training_phase, adaptive_reward, adaptive_gain
        """
        training_info, _ = choiceworld.get_subject_training_info(
            subject_name=self.session_info.SUBJECT_NAME,
            task_name=self.protocol_name,
            stim_gain=self.task_params.AG_INIT_VALUE,
            stim_gain_on_error=self.task_params.STIM_GAIN,
            default_reward=self.task_params.REWARD_AMOUNT_UL,
            local_path=self.iblrig_settings['iblrig_local_data_path'],
            remote_path=self.iblrig_settings['iblrig_remote_data_path'],
            lab=self.iblrig_settings['ALYX_LAB'],
            iblrig_settings=self.iblrig_settings,
        )
        return training_info['training_phase'], training_info['adaptive_reward'], training_info['adaptive_gain']

    def compute_performance(self):
        """Aggregate the trials table to compute the performance of the mouse on each contrast."""
        self.trials_table['signed_contrast'] = self.trials_table.contrast * self.trials_table.position
        performance = self.trials_table.groupby(['signed_contrast']).agg(
            last_50_perf=pd.NamedAgg(column='trial_correct', aggfunc=lambda x: np.sum(x[np.maximum(-50, -x.size) :]) / 50),
            ntrials=pd.NamedAgg(column='trial_correct', aggfunc='count'),
        )
        return performance

    def check_training_phase(self):
        """Check if the mouse is ready to move to the next training phase."""
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
        else:
            self.trials_table.at[self.trial_num, 'debias_trial'] = False
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=self.task_params.PROBABILITY_LEFT, position=position, contrast=contrast)
        self.trials_table.at[self.trial_num, 'training_phase'] = self.training_phase

    def show_trial_log(self, extra_info: dict[str, Any] | None = None, log_level: int = logging.INFO):
        # construct info dict
        info_dict = {
            'Contrast Set': np.unique(np.abs(choiceworld.contrasts_set(self.training_phase))),
            'Training Phase': self.training_phase,
        }

        # update info dict with extra_info dict
        if isinstance(extra_info, dict):
            info_dict.update(extra_info)

        # call parent method
        super().show_trial_log(extra_info=info_dict, log_level=log_level)
