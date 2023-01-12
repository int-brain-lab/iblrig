import datetime
import json
import logging
import math
import random

import numpy as np
import pandas as pd

import iblrig.misc as misc
from iblrig.check_sync_pulses import sync_check
from iblrig.iotasks import ComplexEncoder

from iblrig.base_tasks import ChoiceWorldSession

NTRIALS_INIT = 1000
log = logging.getLogger("iblrig")


class Session(ChoiceWorldSession):
    """"Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""
    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.init_datetime = datetime.datetime.now()
        self.trial_num = -1
        self.block_trial_num = -1
        self.block_num = -1
        self.ntrials_correct = 0
        self.water_delivered = 0
        self.behavior_data = []
        self.movement_left = self.device_rotary_encoder.THRESHOLD_EVENTS[
            self.task_params.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = self.device_rotary_encoder.THRESHOLD_EVENTS[
            self.task_params.QUIESCENCE_THRESHOLDS[1]]

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
            'stim_reverse': np.zeros(NTRIALS_INIT) * np.NaN,
            'stim_sigma': np.zeros(NTRIALS_INIT) * np.NaN,
            'trial_correct': np.zeros(NTRIALS_INIT, dtype=bool),
            'trial_num': np.zeros(NTRIALS_INIT, dtype=np.int16),
        })

        self.as_data = {
            "Temperature_C": -1,
            "AirPressure_mb": -1,
            "RelativeHumidity": -1,
        }
        self.new_block()

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
            self.block_len = 90
        else:
            self.block_len = int(misc.texp(
                factor=self.task_params.BLOCK_LEN_FACTOR,
                min_=self.task_params.BLOCK_LEN_MIN,
                max_=self.task_params.BLOCK_LEN_MAX
            ))

        if self.block_num == 0:
            if self.task_params.BLOCK_INIT_5050:
                self.block_probability_left = 0.5
            else:
                self.block_probability_left = np.random.choice(self.task_params.BLOCK_PROBABILITY_SET)
        elif self.block_num == 1 and self.task_params.BLOCK_INIT_5050:
            self.block_probability_left = np.random.choice(self.task_params.BLOCK_PROBABILITY_SET)
        else:
            # this switches the probability of leftward stim for the next block
            self.block_probability_left = round(abs(1 - self.block_probability_left), 1)

    def next_trial(self):
        # First trial exception
        self.trial_num += 1
        self.block_trial_num += 1
        self.trial_correct = None
        if self.block_trial_num > (self.block_len - 1):
            self.new_block()
        self.trials_table.at[self.trial_num, 'quiescent_period'] = self.draw_quiescent_period()
        self.trials_table.at[self.trial_num, 'contrast'] = self.draw_contrast()
        self.trials_table.at[self.trial_num, 'stim_phase'] = random.uniform(0, 2 * math.pi)
        self.trials_table.at[self.trial_num, 'stim_sigma'] = self.task_params.STIM_SIGMA
        self.trials_table.at[self.trial_num, 'stim_angle'] = self.task_params.STIM_ANGLE
        self.trials_table.at[self.trial_num, 'stim_freq'] = self.task_params.STIM_FREQ
        self.trials_table.at[self.trial_num, 'stim_probability_left'] = self.block_probability_left
        pos = self.draw_position()
        self.trials_table.at[self.trial_num, 'position'] = pos
        self.event_error = self.device_rotary_encoder.THRESHOLD_EVENTS[pos]
        self.event_reward = self.device_rotary_encoder.THRESHOLD_EVENTS[-pos]
        self.send_trial_info_to_bonsai()

    def send_trial_info_to_bonsai(self):
        bonsai_dict = {k: self.trials_table[k][self.trial_num] for k in
                       self.osc_client.OSC_PROTOCOL.keys() if k in self.trials_table.columns}
        self.osc_client.send2bonsai(**bonsai_dict)

    def trial_completed(self, behavior_data):
        """Update outcome variables using bpod.session.current_trial
        Check trial for state entries, first value of first tuple"""
        # Update elapsed_time
        self.behavior_data = behavior_data
        correct = ~np.isnan(self.behavior_data["States timestamps"]["correct"][0][0])
        error = ~np.isnan(self.behavior_data["States timestamps"]["error"][0][0])
        no_go = ~np.isnan(self.behavior_data["States timestamps"]["no_go"][0][0])
        assert correct or error or no_go
        # Add trial's response time to the buffer
        self.trials_table.at[self.trial_num, 'response_time'] = misc.get_trial_rt(self.behavior_data)
        self.trials_table.at[self.trial_num, 'trial_correct'] = bool(correct)
        self.trials_table.at[self.trial_num, 'reward_amount'] = self.task_params.REWARD_AMOUNT

        # Update response buffer -1 for left, 0 for nogo, and 1 for rightward
        # what happens if position is 0?
        position = self.trials_table.at[self.trial_num, 'position']
        if (correct and position < 0) or (error and position > 0):
            response_side = 1
        elif (correct and position > 0) or (error and position < 0):
            response_side = -1
        elif no_go:
            response_side = 0
        self.trials_table.at[self.trial_num, 'response_side'] = response_side

        # SAVE TRIAL DATA
        save_dict = {"behavior_data": behavior_data}
        # Dump and save
        with open(self.paths['DATA_FILE_PATH'], 'a') as fp:
            fp.write(json.dumps(save_dict, cls=ComplexEncoder) + '\n')
        # If more than 42 trials save transfer_me.flag
        if self.trial_num == 42:
            misc.create_flags(self.paths.DATA_FILE_PATH, self.task_params.POOP_COUNT)

    def check_stop_criterions(self):
        return misc.check_stop_criterions(
            self.init_datetime, self.trials_table['response_time'].values(), self.trial_num
        )

    def draw_quiescent_period(self):
        """
        The quiescent period is drawn from a truncated exponential distribution
        """
        return self.task_params.QUIESCENT_PERIOD + misc.texp()

    def draw_contrast(self):
        return misc.draw_contrast(self.task_params.CONTRAST_SET,
                                  self.task_params.CONTRAST_SET_PROBABILITY_TYPE)

    def check_sync_pulses(self):
        return sync_check(self)

    def show_trial_log(self):
        msg = f"""
##########################################
TRIAL NUM:            {self.trial_num}
STIM POSITION:        {self.position}
STIM CONTRAST:        {self.contrast}
STIM PHASE:           {self.stim_phase}

BLOCK NUMBER:         {self.block_num}
BLOCK LENGTH:         {self.block_len}
TRIALS IN BLOCK:      {self.block_trial_num}
STIM PROB LEFT:       {self.stim_probability_left}

RESPONSE TIME:        {self.response_time_buffer[-1]}
TRIAL CORRECT:        {self.trial_correct}

NTRIALS CORRECT:      {self.ntrials_correct}
NTRIALS ERROR:        {self.trial_num - self.ntrials_correct}
WATER DELIVERED:      {np.round(self.water_delivered, 3)} µl
TIME FROM START:      {self.elapsed_time}
TEMPERATURE:          {self.as_data['Temperature_C']} ºC
AIR PRESSURE:         {self.as_data['AirPressure_mb']} mb
RELATIVE HUMIDITY:    {self.as_data['RelativeHumidity']} %
##########################################"""
        log.info(msg)

    def update_probability_left(self):
        return self.block_probability_left

    def draw_position(self, position_set=None, pleft=None):
        position_set = position_set or self.task_params.STIM_POSITIONS
        pleft = pleft or self.block_probability_left
        return int(np.random.choice(position_set, p=[pleft, 1 - pleft]))

    def psychometric_curve(self):
        pd_table = self.trials_table.iloc[:self.trial_num, :].copy()
        pd_table['signed_contrast'] = np.sign(pd_table['position']) * pd_table['contrast']

        psychometric_curves = pd_table.groupby('signed_contrast').agg(
            count=pd.NamedAgg(column="signed_contrast", aggfunc="count"),
            response_time=pd.NamedAgg(column="response_time", aggfunc="mean"),
            performance=pd.NamedAgg(column="trial_correct", aggfunc="mean"),
        )
        return psychometric_curves
