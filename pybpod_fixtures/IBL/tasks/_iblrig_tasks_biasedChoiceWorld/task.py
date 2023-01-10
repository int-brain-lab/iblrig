import datetime
import json
import logging
import math
import random

import numpy as np
import pandas as pd

import iblrig.ambient_sensor as ambient_sensor
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
    def __init__(self, debug=False, fmake=True, **kwargs):
        super(Session, self).__init__(debug=debug, fmake=fmake, **kwargs)

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
            'contrast': np.zeros(NTRIALS_INIT),
            'position': np.zeros(NTRIALS_INIT),
            'quiescent_period': np.zeros(NTRIALS_INIT),
            'response_time': np.zeros(NTRIALS_INIT),
            'stim_angle': np.zeros(NTRIALS_INIT),
            'stim_freq': np.zeros(NTRIALS_INIT),
            'stim_gain': np.zeros(NTRIALS_INIT),
            'stim_sigma': np.zeros(NTRIALS_INIT),
            'stim_reverse': np.zeros(NTRIALS_INIT),
            'stim_phase': np.zeros(NTRIALS_INIT),
            'stim_probability_left': np.zeros(NTRIALS_INIT),
            'trial_num': np.zeros(NTRIALS_INIT, dtype=np.int32),
            'trial_correct': np.zeros(NTRIALS_INIT),
            'reward_amount': np.zeros(NTRIALS_INIT),
            'reward_valve_time': np.zeros(NTRIALS_INIT),
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
                self.block_probability_left = np.random.choice(self.block_probability_set)
        elif self.block_num == 1 and self.task_params.BLOCK_INIT_5050:
            self.block_probability_left = np.random.choice(self.block_probability_set)
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
        self.trials_table['quiescent_period'][self.trial_num] = self.draw_quiescent_period()
        self.trials_table['contrast'][self.trial_num] = self.draw_contrast()
        self.trials_table['stim_phase'][self.trial_num] = random.uniform(0, 2 * math.pi)
        self.trials_table['stim_probability_left'][self.trial_num] = self.block_probability_left
        pos = self.draw_position()
        self.trials_table['position'][self.trial_num] = pos
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
        self.response_time = misc.get_trial_rt(self.behavior_data)
        self.response_time_buffer.append(self.response_time)
        # Update response buffer -1 for left, 0 for nogo, and 1 for rightward
        if (correct and self.position < 0) or (error and self.position > 0):
            self.response_side_buffer.append(1)
        elif (correct and self.position > 0) or (error and self.position < 0):
            self.response_side_buffer.append(-1)
        elif no_go:
            self.response_side_buffer.append(0)
        # Update the trial_correct variable + buffer
        self.trial_correct = bool(correct)
        self.trial_correct_buffer.append(self.trial_correct)
        # Increment the trial correct counter
        self.ntrials_correct += self.trial_correct
        # Update the water delivered
        if self.trial_correct:
            self.water_delivered += self.sph.task_params.REWARD_AMOUNT

        # SAVE TRIAL DATA
        params = self.__dict__.copy()
        params.update({"behavior_data": behavior_data})
        params.pop('sph')
        # Convert to str all non serializable params
        # params["data_file"] = str(params["data_file"])
        params["osc_client"] = "osc_client_pointer"
        params["init_datetime"] = params["init_datetime"].isoformat()
        params["elapsed_time"] = str(self.elapsed_time)
        params["position"] = int(params["position"])
        # Delete buffered data
        params["stim_probability_left_buffer"] = ""
        params["position_buffer"] = ""
        params["contrast_buffer"] = ""
        params["signed_contrast_buffer"] = ""
        params["response_time_buffer"] = ""
        params["response_side_buffer"] = ""
        params["trial_correct_buffer"] = ""
        # Dump and save
        with open(self.sph.paths['DATA_FILE_PATH'], 'a') as fp:
            fp.write(json.dumps(params, cls=ComplexEncoder) + '\n')
        # If more than 42 trials save transfer_me.flag
        if self.trial_num == 42:
            misc.create_flags(self.data_file_path, self.poop_count)

    def check_stop_criterions(self):
        return misc.check_stop_criterions(
            self.init_datetime, self.response_time_buffer, self.trial_num
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

    def save_ambient_sensor_data(self, bpod_instance, destination):
        if self.save_ambient_data:
            self.as_data = ambient_sensor.get_reading(bpod_instance, save_to=destination)
            return self.as_data
        else:
            log.info("Ambient Sensor data disabled in task settings")
            null_measures = {
                "Temperature_C": -1,
                "AirPressure_mb": -1,
                "RelativeHumidity": -1,
            }
            self.as_data = null_measures
            return self.as_data

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
