import datetime
import json
import logging
import math
import random

import numpy as np

import iblrig.ambient_sensor as ambient_sensor
import iblrig.bonsai as bonsai
import iblrig.misc as misc
from iblrig.check_sync_pulses import sync_check
from iblrig.iotasks import ComplexEncoder

from iblrig.base_tasks import ChoiceWorldSessionParamHandler

log = logging.getLogger("iblrig")


class SessionParamHandler(ChoiceWorldSessionParamHandler):
    """"Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""
    def __init__(self, debug=False, fmake=True, **kwargs):
        super(SessionParamHandler, self).__init__(debug=debug, fmake=fmake, **kwargs)


class Task():
    """All trial parameters for the current trial.
    On self.trial_completed a JSON serializable string containing state/event
    data and all the parameters is returned to be printed out and saved by
    pybpod under the stdout flag.
    self.next_trial calls the update functions of all related objects
    """

    def __init__(self, *args, interactive=True, **kwargs):

        self.init_datetime = datetime.datetime.now()
        self.sph = SessionParamHandler(rig_settings_yaml=None, interactive=interactive)

        self.quiescent_period = self.draw_quiescent_period()
        self.as_data = {
            "Temperature_C": -1,
            "AirPressure_mb": -1,
            "RelativeHumidity": -1,
        }
        # Reward amount
        # Initialize parameters that may change every trial
        self.trial_num = 0
        self.stim_phase = 0.0
        self.stim_reverse = 0

        self.block_num = 0
        self.block_trial_num = 0

        if self.sph.task_params.BLOCK_INIT_5050:
            self.block_len = 90
        else:
            self.block_len = self.get_block_len()

        # Position
        self.stim_probability_left = self.init_probability_left()
        self.position = self.draw_position(pleft=self.stim_probability_left)
        # Contrast
        self.contrast = self.draw_contrast()
        # RE event names

        self.event_error = self.sph.device_rotary_encoder.THRESHOLD_EVENTS[self.position]
        self.event_reward = self.sph.device_rotary_encoder.THRESHOLD_EVENTS[-self.position]
        self.movement_left = self.sph.device_rotary_encoder.THRESHOLD_EVENTS[self.sph.task_params.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = self.sph.device_rotary_encoder.THRESHOLD_EVENTS[self.sph.task_params.QUIESCENCE_THRESHOLDS[1]]
        # Trial Completed params
        self.behavior_data = []
        self.response_time = None
        self.response_time_buffer = []
        self.response_side_buffer = []
        self.trial_correct = None
        self.trial_correct_buffer = []
        self.ntrials_correct = 0
        self.water_delivered = 0

    @property
    def elapsed_time(self):
        # elapsed time from init datetime in seconds
        return (datetime.datetime.now() - self.init_datetime).total_seconds()

    @property
    def signed_contrast(self):
        return self.contrast * np.sign(self.position)
    def check_stop_criterions(self):
        return misc.check_stop_criterions(
            self.init_datetime, self.response_time_buffer, self.trial_num
        )

    def draw_quiescent_period(self):
        """
        The quiescent period is drawn from a truncated exponential distribution
        """
        return self.sph.task_params.QUIESCENT_PERIOD + misc.texp()

    def draw_contrast(self):
        return misc.draw_contrast(self.sph.task_params.CONTRAST_SET,
                                  self.sph.task_params.CONTRAST_SET_PROBABILITY_TYPE)

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

    def first_trial(self):
        self.trial_num += 1
        self.block_num += 1
        self.block_trial_num += 1
        # Send next trial info to Bonsai
        bonsai.send_current_trial_info(self)

    def next_trial(self):
        # First trial exception
        if self.trial_num == 0:
            self.first_trial()
            return
        # Increment trial number
        self.trial_num += 1
        # Update quiescent period
        self.quiescent_period = self.draw_quiescent_period()
        # Update stimulus phase
        self.stim_phase = random.uniform(0, 2 * math.pi)
        # Update block
        self = self.update_block_params()
        # Update stim probability left + buffer
        self.stim_probability_left = self.update_probability_left()

        # Update position + buffer
        self.position = self.draw_position()
        # Update contrast + buffer
        self.contrast = self.draw_contrast()
        # Update state machine events


        self.event_error = self.sph.device_rotary_encoder.THRESHOLD_EVENTS[self.position]
        self.event_reward = self.sph.device_rotary_encoder.THRESHOLD_EVENTS[-self.position]

        # Reset outcome variables for next trial
        self.trial_correct = None
        # Send next trial info to Bonsai
        bonsai.send_current_trial_info(self)

    def trial_completed(self, behavior_data):
        """Update outcome variables using bpod.session.current_trial
        Check trial for state entries, first value of first tuple"""
        # Update elapsed_time
        self.elapsed_time = datetime.datetime.now() - self.init_datetime
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
            self.water_delivered += self.reward_amount

        # SAVE TRIAL DATA
        params = self.__dict__.copy()
        params.update({"behavior_data": behavior_data})
        # Convert to str all non serializable params
        params["data_file"] = str(params["data_file"])
        params["osc_client"] = "osc_client_pointer"
        params["init_datetime"] = params["init_datetime"].isoformat()
        params["elapsed_time"] = str(params["elapsed_time"])
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
        out = json.dumps(params, cls=ComplexEncoder)
        self.data_file.write(out)
        self.data_file.write("\n")
        self.data_file.close()
        # If more than 42 trials save transfer_me.flag
        if self.trial_num == 42:
            misc.create_flags(self.data_file_path, self.poop_count)

        return self

    def get_block_len(self, factor=None, min_=None, max_=None):
        factor = factor or self.sph.task_params.BLOCK_LEN_FACTOR
        min_ = min_ or self.sph.task_params.BLOCK_LEN_MIN
        max_ = max_ or self.sph.task_params.BLOCK_LEN_MAX
        return int(misc.texp(factor=factor, min_=min_, max_=max_))

    def update_block_params(self):
        self.block_trial_num += 1
        if self.block_trial_num > self.block_len:
            self.block_num += 1
            self.block_trial_num = 1
            self.block_len = self.get_block_len(
                factor=self.block_len_factor, min_=self.block_len_min, max_=self.block_len_max
            )
        return self

    def update_probability_left(tph):
        if tph.block_trial_num != 1:
            return tph.stim_probability_left

        if tph.block_num == 1 and tph.block_init_5050:
            return 0.5
        elif tph.block_num == 1 and not tph.block_init_5050:
            return np.random.choice(tph.block_probability_set)
        elif tph.block_num == 2 and tph.block_init_5050:
            return np.random.choice(tph.block_probability_set)
        else:
            return round(abs(1 - tph.stim_probability_left), 1)

    def draw_position(self, position_set=None, pleft=None):
        position_set = position_set or self.sph.task_params.STIM_POSITIONS
        pleft = pleft or self.stim_probability_left
        return int(np.random.choice(position_set, p=[pleft, 1 - pleft]))

    def init_probability_left(self):
        if self.sph.task_params.BLOCK_INIT_5050:
            return 0.5
        else:
            return np.random.choice(self.sph.task_params.BLOCK_PROBABILITY_SET)

    def calc_probability_left(tph):
        if tph.block_num == 1:
            out = 0.5
        elif tph.block_num == 2:
            spos = np.sign(tph.position_buffer)
            low = tph.len_blocks_buffer[0]
            high = tph.len_blocks_buffer[0] + tph.len_blocks_buffer[1]
            if np.sum(spos[low:high]) / tph.len_blocks_buffer[1] > 0:
                out = 0.2
            else:
                out = 0.8
        else:
            out = np.round(np.abs(1 - tph.stim_probability_left), 1)
        return out
