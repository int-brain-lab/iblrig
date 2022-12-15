import datetime
import json
import logging
import math
import random

import numpy as np
from dateutil import parser

import iblrig.ambient_sensor as ambient_sensor
import iblrig.blocks as blocks
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


class TrialParamHandler(object):
    """All trial parameters for the current trial.
    On self.trial_completed a JSON serializable string containing state/event
    data and all the parameters is returned to be printed out and saved by
    pybpod under the stdout flag.
    self.next_trial calls the update functions of all related objects
    """

    def __init__(self, sph):
        # Constants from settings
        self.session_start_delay_sec = sph.SESSION_START_DELAY_SEC
        self.init_datetime = parser.parse(sph.PYBPOD_SESSION) + datetime.timedelta(
            0, self.session_start_delay_sec
        )
        self.task_protocol = sph.PYBPOD_PROTOCOL
        self.data_file_path = sph.DATA_FILE_PATH
        self.data_file = open(self.data_file_path, "a")
        self.position_set = sph.STIM_POSITIONS
        self.contrast_set = sph.CONTRAST_SET
        self.contrast_set_probability_type = sph.CONTRAST_SET_PROBABILITY_TYPE
        self.repeat_on_error = sph.REPEAT_ON_ERROR
        self.threshold_events_dict = sph.ROTARY_ENCODER.THRESHOLD_EVENTS
        self.quiescent_period_base = sph.QUIESCENT_PERIOD
        self.quiescent_period = self.quiescent_period_base + misc.texp()
        self.response_window = sph.RESPONSE_WINDOW
        self.interactive_delay = sph.INTERACTIVE_DELAY
        self.iti_error = sph.ITI_ERROR
        self.iti_correct_target = sph.ITI_CORRECT
        self.osc_client = sph.OSC_CLIENT
        self.stim_freq = sph.STIM_FREQ
        self.stim_angle = sph.STIM_ANGLE
        self.stim_gain = sph.STIM_GAIN
        self.stim_sigma = sph.STIM_SIGMA
        self.out_tone = sph.OUT_TONE
        self.out_noise = sph.OUT_NOISE
        self.out_stop_sound = sph.OUT_STOP_SOUND
        self.poop_count = sph.POOP_COUNT
        self.save_ambient_data = sph.RECORD_AMBIENT_SENSOR_DATA
        self.as_data = {
            "Temperature_C": -1,
            "AirPressure_mb": -1,
            "RelativeHumidity": -1,
        }
        # Reward amount
        self.reward_amount = sph.REWARD_AMOUNT
        self.reward_valve_time = sph.REWARD_VALVE_TIME
        self.iti_correct = self.iti_correct_target - self.reward_valve_time
        # Initialize parameters that may change every trial
        self.trial_num = 0
        self.stim_phase = 0.0
        self.stim_reverse = 0

        self.block_num = 0
        self.block_trial_num = 0
        self.block_len_factor = sph.BLOCK_LEN_FACTOR
        self.block_len_min = sph.BLOCK_LEN_MIN
        self.block_len_max = sph.BLOCK_LEN_MAX
        self.block_probability_set = sph.BLOCK_PROBABILITY_SET
        self.block_init_5050 = sph.BLOCK_INIT_5050
        self.block_len = blocks.init_block_len(self)
        # Position
        self.stim_probability_left = blocks.init_probability_left(self)
        self.stim_probability_left_buffer = [self.stim_probability_left]
        self.position = blocks.draw_position(self.position_set, self.stim_probability_left)
        self.position_buffer = [self.position]
        # Contrast
        self.contrast = misc.draw_contrast(self.contrast_set)
        self.contrast_buffer = [self.contrast]
        self.signed_contrast = self.contrast * np.sign(self.position)
        self.signed_contrast_buffer = [self.signed_contrast]
        # RE event names
        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
        self.movement_left = self.threshold_events_dict[sph.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = self.threshold_events_dict[sph.QUIESCENCE_THRESHOLDS[1]]
        # Trial Completed params
        self.elapsed_time = 0
        self.behavior_data = []
        self.response_time = None
        self.response_time_buffer = []
        self.response_side_buffer = []
        self.trial_correct = None
        self.trial_correct_buffer = []
        self.ntrials_correct = 0
        self.water_delivered = 0

    def check_stop_criterions(self):
        return misc.check_stop_criterions(
            self.init_datetime, self.response_time_buffer, self.trial_num
        )

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

    def next_trial(self):
        # First trial exception
        if self.trial_num == 0:
            self.trial_num += 1
            self.block_num += 1
            self.block_trial_num += 1
            # Send next trial info to Bonsai
            bonsai.send_current_trial_info(self)
            return
        self.data_file = str(self.data_file)
        # Increment trial number
        self.trial_num += 1
        # Update quiescent period
        self.quiescent_period = self.quiescent_period_base + misc.texp()
        # Update stimulus phase
        self.stim_phase = random.uniform(0, 2 * math.pi)
        # Update block
        self = blocks.update_block_params(self)
        # Update stim probability left + buffer
        self.stim_probability_left = blocks.update_probability_left(self)
        self.stim_probability_left_buffer.append(self.stim_probability_left)
        # Update position + buffer
        self.position = blocks.draw_position(self.position_set, self.stim_probability_left)
        self.position_buffer.append(self.position)
        # Update contrast + buffer
        self.contrast = misc.draw_contrast(
            self.contrast_set, prob_type=self.contrast_set_probability_type
        )
        self.contrast_buffer.append(self.contrast)
        # Update signed_contrast + buffer (AFTER position update)
        self.signed_contrast = self.contrast * np.sign(self.position)
        self.signed_contrast_buffer.append(self.signed_contrast)
        # Update state machine events
        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
        # Reset outcome variables for next trial
        self.trial_correct = None
        # Open the data file to append the next trial
        self.data_file = open(self.data_file_path, "a")
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


class Task():
    """

    """

    def __init__(self, *args, interactive=True, **kwargs):
        self.sph = SessionParamHandler(rig_settings_yaml=None, interactive=interactive)
