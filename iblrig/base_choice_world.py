"""
This modules extends the base_tasks modules by providing task logic around the Choice World protocol
"""
from abc import abstractmethod
import json
import math
import random
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from iblutil.util import Bunch

import iblrig.base_tasks
import iblrig.iotasks as iotasks
import iblrig.user_input as user
import iblrig.misc as misc

log = logging.getLogger(__name__)

NTRIALS_INIT = 2000
NBLOCKS_INIT = 100
# todo sess update plots
# todo camera mixin: choose modality


class OnlineGraphsMixin(object):

    def update_plots(self):
        pass
        # stop_crit = self.check_stop_criterions()
        # # clean this up and remove display from logic
        # if stop_crit and self.task_params.USE_AUTOMATIC_STOPPING_CRITERIONS:
        #     if stop_crit == 1:
        #         msg = "STOPPING CRITERIA Nº1: PLEASE STOP TASK AND REMOVE MOUSE\
        #         \n < 400 trials in 45min"
        #         f.patch.set_facecolor("xkcd:mint green")
        #     elif stop_crit == 2:
        #         msg = "STOPPING CRITERIA Nº2: PLEASE STOP TASK AND REMOVE MOUSE\
        #         \nMouse seems to be inactive"
        #         f.patch.set_facecolor("xkcd:yellow")
        #     elif stop_crit == 3:
        #         msg = "STOPPING CRITERIA Nº3: PLEASE STOP TASK AND REMOVE MOUSE\
        #         \n> 90 minutes have passed since session start"
        #         f.patch.set_facecolor("xkcd:red")
        #
        #     if not self.task_params.SUBJECT_DISENGAGED_TRIGGERED and stop_crit:
        #         patch = {
        #             "SUBJECT_DISENGAGED_TRIGGERED": stop_crit,
        #             "SUBJECT_DISENGAGED_TRIALNUM": i + 1,
        #         }
        #         self.paths.patch_settings_file(patch)
        #     [log.warning(msg) for x in range(5)]


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
    base_parameters_file = Path(__file__).parent.joinpath('base_choice_world_params.yaml')

    def __init__(self, interactive=False, *args, **kwargs):
        super(ChoiceWorldSession, self).__init__(*args, **kwargs)
        self.interactive = interactive

        # Session data
        if self.interactive:
            self.SUBJECT_WEIGHT = user.ask_subject_weight(self.pybpod_settings.PYBPOD_SUBJECTS[0])
            self.task_params.SESSION_START_DELAY_SEC = user.ask_session_delay(self.paths.SETTINGS_FILE_PATH)
        else:
            self.SUBJECT_WEIGHT = np.NaN
        self.display_logs()
        # init behaviour data
        self.movement_left = self.device_rotary_encoder.THRESHOLD_EVENTS[
            self.task_params.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = self.device_rotary_encoder.THRESHOLD_EVENTS[
            self.task_params.QUIESCENCE_THRESHOLDS[1]]
        # init counter variables
        self.trial_num = -1
        self.block_num = -1
        self.block_trial_num = -1
        # init the tables, there are 3 of them: a block table, a trials table and a ambient sensor data table
        self.blocks_table = pd.DataFrame({
            'probability_left': np.zeros(NBLOCKS_INIT) * np.NaN,
            'block_length': np.zeros(NBLOCKS_INIT, dtype=np.int16) * -1,
        })
        self.trials_table = pd.DataFrame({
            'block_num': np.zeros(NTRIALS_INIT, dtype=np.int16),
            'block_trial_num': np.zeros(NTRIALS_INIT, dtype=np.int16),
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
            'stim_probability_left': np.zeros(NTRIALS_INIT),
            'stim_reverse': np.zeros(NTRIALS_INIT, dtype=bool),
            'stim_sigma': np.zeros(NTRIALS_INIT) * np.NaN,
            'trial_correct': np.zeros(NTRIALS_INIT, dtype=bool),
            'trial_num': np.zeros(NTRIALS_INIT, dtype=np.int16),
        })

        self.ambient_sensor_table = pd.DataFrame({
            "Temperature_C": np.zeros(NTRIALS_INIT) * np.NaN,
            "AirPressure_mb": np.zeros(NTRIALS_INIT) * np.NaN,
            "RelativeHumidity": np.zeros(NTRIALS_INIT) * np.NaN,
        })
        self.aggregates = Bunch({
            'ntrials_correct': 0,
            'water_delivered': 0,
        })

    def start(self):
        """
        In this step we explicitly run the start methods of the various mixins.
        The super class start method is overloaded because we need to start the different hardware pieces in order
        """
        self.start_mixin_frame2ttl()
        self.start_mixin_bpod()
        self.start_mixin_valve()
        self.start_mixin_sound()
        self.start_mixin_rotary_encoder()
        self.start_mixin_bonsai_cameras()
        self.start_mixin_bonsai_microphone()
        self.start_mixin_bonsai_visual_stimulus()

        # create the task parameter file in the raw_behavior dir
        self.output_task_parameters_to_json_file()

    """
    Those are the methods that need to be implemented for a new task
    """
    @abstractmethod
    def new_block(self):
        pass

    @abstractmethod
    def next_trial(self):
        pass

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

    def send_trial_info_to_bonsai(self):
        """
        This sends the trial information to the Bonsai UDP port for the stimulus
        The OSC protocol is documented in iblrig.base_tasks.BonsaiVisualStimulusMixin
        """
        bonsai_viz_client = self.bonsai_stimulus['udp_client']
        bonsai_dict = {k: self.trials_table[k][self.trial_num] for k in
                       bonsai_viz_client.OSC_PROTOCOL
                       if k in self.trials_table.columns}
        bonsai_viz_client.send2bonsai(**bonsai_dict)

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
        self.trials_table.at[self.trial_num, 'response_time'] = misc.get_trial_rt(bpod_data)
        # get the trial outcome
        state_names = ['correct', 'error', 'no_go', 'omit_correct', 'omit_error', 'omit_no_go']
        outcome = {sn: ~np.isnan(bpod_data['States timestamps'].get(sn, [[np.NaN]])[0][0]) for sn in state_names}
        assert np.sum(list(outcome.values())) == 1
        outcome = next(k for k in outcome if outcome[k])
        # if the reward state has not been triggered, null the reward
        if np.isnan(bpod_data['States timestamps']['reward'][0][0]):
            self.trials_table.at[self.trial_num, 'reward_amount'] = 0
        self.trials_table.at[self.trial_num, 'reward_valve_time'] = self.reward_time
        # update cumulative reward value
        self.aggregates.water_delivered += self.trials_table.at[self.trial_num, 'reward_amount']
        # Update response buffer -1 for left, 0 for nogo, and 1 for rightward
        position = self.trials_table.at[self.trial_num, 'position']
        if 'correct' in outcome:
            self.trials_table.at[self.trial_num, 'trial_correct'] = True
            self.aggregates.ntrials_correct += 1
            self.trials_table.at[self.trial_num, 'response_side'] = -np.sign(position)
        elif 'error' in outcome:
            self.trials_table.at[self.trial_num, 'response_side'] = np.sign(position)
        elif 'no_go' in outcome:
            self.trials_table.at[self.trial_num, 'response_side'] = 0
        else:
            ValueError("The task outcome doesn't contain no_go, error or correct")
        assert position != 0, "the position value should be either 35 or -35"
        # SAVE TRIAL DATA
        save_dict = self.trials_table.iloc[self.trial_num].to_dict()
        save_dict["behavior_data"] = bpod_data
        # Dump and save
        with open(self.paths['DATA_FILE_PATH'], 'a') as fp:
            fp.write(json.dumps(save_dict, cls=iotasks.ComplexEncoder) + '\n')
        # If more than 42 trials save transfer_me.flag
        if self.trial_num == 42:
            misc.create_flags(self.paths.DATA_FILE_PATH, self.task_params.POOP_COUNT)
        self.check_sync_pulses(bpod_data=bpod_data)

    def check_stop_criterions(self):
        return misc.check_stop_criterions(
            self.init_datetime, self.trials_table['response_time'].values(), self.trial_num
        )

    def check_sync_pulses(self, bpod_data):
        # todo move this in the post trial when we have a task flow
        if not self.bpod.is_connected:
            return
        events = bpod_data["Events timestamps"]
        ev_bnc1 = misc.get_port_events(events, name="BNC1")
        ev_bnc2 = misc.get_port_events(events, name="BNC2")
        ev_port1 = misc.get_port_events(events, name="Port1")
        NOT_FOUND = "COULD NOT FIND DATA ON {}"
        bnc1_msg = NOT_FOUND.format("BNC1") if not ev_bnc1 else "OK"
        bnc2_msg = NOT_FOUND.format("BNC2") if not ev_bnc2 else "OK"
        port1_msg = NOT_FOUND.format("Port1") if not ev_port1 else "OK"
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

    def show_trial_log(self):
        trial_info = self.trials_table.iloc[self.trial_num]
        msg = f"""
##########################################
TRIAL NUM:            {trial_info.trial_num}
STIM POSITION:        {trial_info.position}
STIM CONTRAST:        {trial_info.contrast}
STIM PHASE:           {trial_info.stim_phase}

BLOCK NUMBER:         {trial_info.block_num}
BLOCK LENGTH:         {self.blocks_table.loc[self.block_num, 'block_length']}
TRIALS IN BLOCK:      {trial_info.block_trial_num}
STIM PROB LEFT:       {trial_info.stim_probability_left}

RESPONSE TIME:        {trial_info.response_time}
TRIAL CORRECT:        {trial_info.trial_correct}

NTRIALS CORRECT:      {self.aggregates.ntrials_correct}
NTRIALS ERROR:        {self.trial_num - self.aggregates.ntrials_correct}
WATER DELIVERED:      {np.round(self.aggregates.water_delivered, 3)} µl
TIME FROM START:      {self.time_elapsed}
TEMPERATURE:          {self.ambient_sensor_table.loc[self.trial_num, 'Temperature_C']} ºC
AIR PRESSURE:         {self.ambient_sensor_table.loc[self.trial_num, 'AirPressure_mb']} mb
RELATIVE HUMIDITY:    {self.ambient_sensor_table.loc[self.trial_num, 'RelativeHumidity']} %
##########################################"""
        log.info(msg)

    def psychometric_curve(self):
        pd_table = self.trials_table.iloc[:self.trial_num, :].copy()
        pd_table['signed_contrast'] = np.sign(pd_table['position']) * pd_table['contrast']

        psychometric_curves = pd_table.groupby('signed_contrast').agg(
            count=pd.NamedAgg(column="signed_contrast", aggfunc="count"),
            response_time=pd.NamedAgg(column="response_time", aggfunc="mean"),
            performance=pd.NamedAgg(column="trial_correct", aggfunc="mean"),
        )
        return psychometric_curves

    @property
    def iti_reward(self, assert_calibration=True):
        """
        Returns the ITI time that needs to be set in order to achieve the desired ITI,
        by subtracting the time it takes to give a reward from the desired ITI.
        """
        if assert_calibration:
            assert 'REWARD_VALVE_TIME' in self.calibration.keys(), 'Reward valve time not calibrated'
        return self.task_params.ITI_CORRECT - self.calibration.get('REWARD_VALVE_TIME', None)

    def display_logs(self):
        if self.paths.PREVIOUS_DATA_FILE:
            msg = f"""
##########################################
PREVIOUS SESSION FOUND
LOADING PARAMETERS FROM:       {self.PREVIOUS_DATA_FILE}
PREVIOUS NTRIALS:              {self.LAST_TRIAL_DATA["trial_num"]}
PREVIOUS WATER DRANK:          {self.LAST_TRIAL_DATA["water_delivered"]}
LAST REWARD:                   {self.LAST_TRIAL_DATA["reward_amount"]}
LAST GAIN:                     {self.LAST_TRIAL_DATA["stim_gain"]}
PREVIOUS WEIGHT:               {self.LAST_SETTINGS_DATA["SUBJECT_WEIGHT"]}
##########################################"""
            log.info(msg)


class BiasedChoiceWorldSession(ChoiceWorldSession):

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
            block_len = int(misc.texp(
                factor=self.task_params.BLOCK_LEN_FACTOR,
                min_=self.task_params.BLOCK_LEN_MIN,
                max_=self.task_params.BLOCK_LEN_MAX
            ))
        if self.block_num == 0:
            if self.task_params.BLOCK_INIT_5050:
                pleft = 0.5
            else:
                pleft = np.random.choice(self.task_params.BLOCK_PROBABILITY_SET)
        elif self.block_num == 1 and self.task_params.BLOCK_INIT_5050:
            pleft = np.random.choice(self.task_params.BLOCK_PROBABILITY_SET)
        else:
            # this switches the probability of leftward stim for the next block
            pleft = round(abs(1 - self.blocks_table.loc[self.block_num - 1, 'probability_left']), 1)
        self.blocks_table.at[self.block_num, 'block_length'] = block_len
        self.blocks_table.at[self.block_num, 'probability_left'] = pleft

    def next_trial(self):
        # First trial exception
        self.trial_num += 1
        self.block_trial_num += 1
        self.trial_correct = None
        if self.block_num < 0 or self.block_trial_num > (self.blocks_table.loc[self.block_num, 'block_length'] - 1):
            self.new_block()
        pleft = self.blocks_table.loc[self.block_num, 'probability_left']
        contrast = misc.draw_contrast(self.task_params.CONTRAST_SET, self.task_params.CONTRAST_SET_PROBABILITY_TYPE)
        position = int(np.random.choice(self.task_params.STIM_POSITIONS, p=[pleft, 1 - pleft]))
        quiescent_period = self.task_params.QUIESCENT_PERIOD + misc.texp(factor=0.35, min_=0.2, max_=0.5)
        self.trials_table.at[self.trial_num, 'quiescent_period'] = quiescent_period
        self.trials_table.at[self.trial_num, 'contrast'] = contrast
        self.trials_table.at[self.trial_num, 'stim_phase'] = random.uniform(0, 2 * math.pi)
        self.trials_table.at[self.trial_num, 'stim_sigma'] = self.task_params.STIM_SIGMA
        self.trials_table.at[self.trial_num, 'stim_angle'] = self.task_params.STIM_ANGLE
        self.trials_table.at[self.trial_num, 'stim_gain'] = self.task_params.STIM_GAIN
        self.trials_table.at[self.trial_num, 'block_num'] = self.block_num
        self.trials_table.at[self.trial_num, 'block_trial_num'] = self.block_trial_num
        self.trials_table.at[self.trial_num, 'stim_freq'] = self.task_params.STIM_FREQ
        self.trials_table.at[self.trial_num, 'stim_probability_left'] = pleft
        self.trials_table.at[self.trial_num, 'trial_num'] = self.trial_num
        self.trials_table.at[self.trial_num, 'position'] = position
        self.trials_table.at[self.trial_num, 'reward_amount'] = self.task_params.REWARD_AMOUNT_UL
        self.send_trial_info_to_bonsai()