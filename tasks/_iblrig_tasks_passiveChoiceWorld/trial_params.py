#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 14:06:34
import datetime
import json
import logging
import time

import numpy as np
from dateutil import parser

import iblrig.ambient_sensor as ambient_sensor
import iblrig.blocks as blocks
import iblrig.bonsai as bonsai
import iblrig.misc as misc
from iblrig.check_sync_pulses import sync_check
from iblrig.iotasks import ComplexEncoder

log = logging.getLogger('iblrig')


class TrialParamHandler(object):
    """All trial parameters for the current trial.
    On self.trial_completed a JSON serializable string containing state/event
    data and all the parameters is returned to be printed out and saved by
    pybpod under the stdout flag.
    self.next_trial calls the update functions of all related objects
    """
    def __init__(self, sph):
        # Constants from settings
        self.init_datetime = parser.parse(sph.PYBPOD_SESSION)
        self.task_protocol = sph.PYBPOD_PROTOCOL
        self.data_file_path = sph.DATA_FILE_PATH
        self.data_file = open(self.data_file_path, 'a')
        self.position_set = sph.STIM_POSITIONS
        self.contrast_set = sph.CONTRAST_SET
        self.contrast_set_probability_type = sph.CONTRAST_SET_PROBABILITY_TYPE
        self.repeat_on_error = sph.REPEAT_ON_ERROR
        self.threshold_events_dict = sph.ROTARY_ENCODER.THRESHOLD_EVENTS
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
        self.as_data = {'Temperature_C': -1, 'AirPressure_mb': -1,
                        'RelativeHumidity': -1}
        # Reward amount
        self.reward_amount = sph.REWARD_AMOUNT
        self.reward_valve_time = sph.REWARD_VALVE_TIME
        self.iti_correct = self.iti_correct_target - self.reward_valve_time
        # Initialize parameters that may change every trial
        self.trial_num = 0
        self.position_buffer = sph.POSITIONS
        self.contrast_buffer = sph.CONTRASTS
        self.quiescent_period_buffer = sph.QUIESCENT_PERIOD
        self.stim_phase_buffer = sph.STIM_PHASE
        self.len_blocks_buffer = sph.LEN_BLOCKS

        self.position = int(self.position_buffer[0])
        self.contrast = self.contrast_buffer[0]
        self.quiescent_period = self.quiescent_period_buffer[0]
        self.stim_phase = self.stim_phase_buffer[0]
        self.block_len = self.len_blocks_buffer[0]

        self.block_num = 0
        self.block_trial_num = 0

        self.stim_probability_left = 0.5
        self.stim_probability_left_buffer = [self.stim_probability_left]
        self.signed_contrast = self.contrast * np.sign(self.position)
        self.signed_contrast_buffer = [self.signed_contrast]
        # RE event names
        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
        self.movement_left = (
            self.threshold_events_dict[sph.QUIESCENCE_THRESHOLDS[0]])
        self.movement_right = (
            self.threshold_events_dict[sph.QUIESCENCE_THRESHOLDS[1]])
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
            self.init_datetime, self.response_time_buffer, self.trial_num)

    def check_sync_pulses(self):
        return sync_check(self)

    def save_ambient_sensor_data(self, bpod_instance, destination):
        if self.save_ambient_data:
            self.as_data = ambient_sensor.get_reading(
                bpod_instance, save_to=destination)
            return self.as_data
        else:
            log.info('Ambient Sensor data disabled in task settings')
            null_measures = {'Temperature_C': -1, 'AirPressure_mb': -1,
                             'RelativeHumidity': -1}
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
        self.quiescent_period = self.quiescent_period_buffer[self.trial_num - 1]
        # Update stimulus phase
        self.stim_phase = self.stim_phase_buffer[self.trial_num - 1]
        # Update block
        self.block_trial_num += 1
        if self.block_trial_num > self.block_len:
            self.block_num += 1
            self.block_trial_num = 1
            self.block_len = self.len_blocks_buffer[self.block_num - 1]
        # Update stim probability left + buffer
        self.stim_probability_left = blocks.calc_probability_left(self)
        self.stim_probability_left_buffer.append(self.stim_probability_left)
        # Update position + buffer
        self.position = int(self.position_buffer[self.trial_num - 1])
        # Update contrast + buffer
        self.contrast = self.contrast_buffer[self.trial_num - 1]
        # Update signed_contrast + buffer (AFTER position update)
        self.signed_contrast = self.contrast * np.sign(self.position)
        self.signed_contrast_buffer.append(self.signed_contrast)
        # Update state machine events
        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
        # Reset outcome variables for next trial
        self.trial_correct = None
        # Open the data file to append the next trial
        self.data_file = open(self.data_file_path, 'a')
        # Send next trial info to Bonsai
        bonsai.send_current_trial_info(self)

    def trial_completed(self, behavior_data):
        """Update outcome variables using bpod.session.current_trial
        Check trial for state entries, first value of first tuple"""
        # Update elapsed_time
        self.elapsed_time = datetime.datetime.now() - self.init_datetime
        self.behavior_data = behavior_data
        correct = ~np.isnan(
            self.behavior_data['States timestamps']['correct'][0][0])
        error = ~np.isnan(
            self.behavior_data['States timestamps']['error'][0][0])
        no_go = ~np.isnan(
            self.behavior_data['States timestamps']['no_go'][0][0])
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
        params.update({'behavior_data': behavior_data})
        # Convert to str all non serializable params
        params['data_file'] = str(params['data_file'])
        params['osc_client'] = 'osc_client_pointer'
        params['init_datetime'] = params['init_datetime'].isoformat()
        params['elapsed_time'] = str(params['elapsed_time'])
        params['position'] = int(params['position'])
        # Delete buffered data
        params['stim_probability_left_buffer'] = ''
        params['position_buffer'] = ''
        params['contrast_buffer'] = ''
        params['signed_contrast_buffer'] = ''
        params['response_time_buffer'] = ''
        params['response_side_buffer'] = ''
        params['trial_correct_buffer'] = ''
        params['quiescent_period_buffer'] = ''
        params['stim_phase_buffer'] = ''
        params['len_blocks_buffer'] = ''
        # Dump and save
        out = json.dumps(params, cls=ComplexEncoder)
        self.data_file.write(out)
        self.data_file.write('\n')
        self.data_file.close()
        # If more than 42 trials save transfer_me.flag
        if self.trial_num == 42:
            misc.create_flags(self.data_file_path, self.poop_count)

        return self


if __name__ == '__main__':
    from session_params import SessionParamHandler
    from sys import platform
    import matplotlib.pyplot as plt
    import online_plots as op
    import task_settings as _task_settings
    import scratch._user_settings as _user_settings
    dt = datetime.datetime.now()
    dt = [str(dt.year), str(dt.month), str(dt.day),
          str(dt.hour), str(dt.minute), str(dt.second)]
    dt = [x if int(x) >= 10 else '0' + x for x in dt]
    dt.insert(3, '-')
    _user_settings.PYBPOD_SESSION = ''.join(dt)
    _user_settings.PYBPOD_SETUP = 'biasedChoiceWorld'
    _user_settings.PYBPOD_PROTOCOL = '_iblrig_tasks_biasedChoiceWorld'
    if platform == 'linux':
        r = "/home/nico/Projects/IBL/github/iblrig"
        _task_settings.IBLRIG_FOLDER = r
        d = "/home/nico/Projects/IBL/github/iblrig/scratch/test_iblrig_data"  # noqa
        _task_settings.IBLRIG_DATA_FOLDER = d
        _task_settings.AUTOMATIC_CALIBRATION = False
        _task_settings.USE_VISUAL_STIMULUS = False
        _task_settings.BLOCK_INIT_5050 = True

    sph = SessionParamHandler(_task_settings, _user_settings, debug=False)
    tph = TrialParamHandler(sph)

    correct_trial = {'Bpod start timestamp': 0.0, 'Trial start timestamp': 15.570999999999998, 'Trial end timestamp': 50.578703, 'States timestamps': {'trial_start': [[15.570999999999998, 15.571099999999998]], 'reset_rotary_encoder': [[15.571099999999998, 15.571199999999997], [15.671399999999998, 15.671499999999998], [15.765699999999999, 15.765799999999999], [15.793999999999997, 15.794099999999997], [15.8112, 15.8113], [15.825199999999999, 15.825299999999999], [15.838099999999997, 15.838199999999997], [15.851599999999998, 15.851699999999997], [15.871199999999998, 15.871299999999998], [15.946299999999997, 15.946399999999997], [16.0142, 16.0143], [16.036699999999996, 16.0368], [16.055, 16.0551], [16.0708, 16.070899999999998], [16.0858, 16.0859], [16.099999999999998, 16.100099999999998], [16.1147, 16.1148], [16.1316, 16.1317], [16.150999999999996, 16.1511], [16.171599999999998, 16.171699999999998], [16.192899999999998, 16.192999999999998], [16.214899999999997, 16.214999999999996], [16.238599999999998, 16.238699999999998], [16.263399999999997, 16.263499999999997], [16.2901, 16.2902], [16.3163, 16.316399999999998], [16.3401, 16.3402], [16.362699999999997, 16.362799999999996], [16.385499999999997, 16.385599999999997], [16.4121, 16.4122], [16.4976, 16.4977], [16.542299999999997, 16.542399999999997], [16.615899999999996, 16.616], [16.9041, 16.9042]], 'quiescent_period': [[15.571199999999997, 15.671399999999998], [15.671499999999998, 15.765699999999999], [15.765799999999999, 15.793999999999997], [15.794099999999997, 15.8112], [15.8113, 15.825199999999999], [15.825299999999999, 15.838099999999997], [15.838199999999997, 15.851599999999998], [15.851699999999997, 15.871199999999998], [15.871299999999998, 15.946299999999997], [15.946399999999997, 16.0142], [16.0143, 16.036699999999996], [16.0368, 16.055], [16.0551, 16.0708], [16.070899999999998, 16.0858], [16.0859, 16.099999999999998], [16.100099999999998, 16.1147], [16.1148, 16.1316], [16.1317, 16.150999999999996], [16.1511, 16.171599999999998], [16.171699999999998, 16.192899999999998], [16.192999999999998, 16.214899999999997], [16.214999999999996, 16.238599999999998], [16.238699999999998, 16.263399999999997], [16.263499999999997, 16.2901], [16.2902, 16.3163], [16.316399999999998, 16.3401], [16.3402, 16.362699999999997], [16.362799999999996, 16.385499999999997], [16.385599999999997, 16.4121], [16.4122, 16.4976], [16.4977, 16.542299999999997], [16.542399999999997, 16.615899999999996], [16.616, 16.9041], [16.9042, 17.3646]], 'stim_on': [[17.3646, 17.464599999999997]], 'reset2_rotary_encoder': [[17.464599999999997, 17.464699999999997]], 'closed_loop': [[17.464699999999997, 49.5787]], 'reward': [[49.5787, 49.7357]], 'correct': [[49.7357, 50.5787]], 'no_go': [[np.nan, np.nan]], 'error': [[np.nan, np.nan]]}, 'Events timestamps': {'Tup': [15.571099999999998, 15.571199999999997, 15.671499999999998, 15.765799999999999, 15.794099999999997, 15.8113, 15.825299999999999, 15.838199999999997, 15.851699999999997, 15.871299999999998, 15.946399999999997, 16.0143, 16.0368, 16.0551, 16.070899999999998, 16.0859, 16.100099999999998, 16.1148, 16.1317, 16.1511, 16.171699999999998, 16.192999999999998, 16.214999999999996, 16.238699999999998, 16.263499999999997, 16.2902, 16.316399999999998, 16.3402, 16.362799999999996, 16.385599999999997, 16.4122, 16.4977, 16.542399999999997, 16.616, 16.9042, 17.3646, 17.464599999999997, 17.464699999999997, 49.7357, 50.5787], 'BNC1Low': [15.637299999999996, 17.5215, 18.539299999999997, 19.436799999999998, 19.5706, 20.554499999999997, 21.504299999999997, 22.6711, 25.2047, 26.254399999999997, 26.7207, 29.3714, 29.8217, 30.9204, 30.986399999999996, 31.387700000000002, 31.770000000000003, 31.9047, 32.5047, 32.6044, 33.8876, 33.9882, 34.1033, 34.1703, 34.5395, 35.62, 36.7697, 37.236, 37.2703, 37.305, 37.3701, 37.4382, 37.7558, 38.1703, 38.3527, 38.4197, 38.5538, 38.620200000000004, 39.936699999999995, 40.6881, 41.7549, 42.5024, 42.585, 43.035999999999994, 44.1039, 49.2046, 49.4698, 49.5368, 49.6195], 'RotaryEncoder1_4': [15.671399999999998, 15.765699999999999, 15.793999999999997, 15.8112, 15.825199999999999, 15.838099999999997, 15.851599999999998, 15.871199999999998, 15.946299999999997, 16.0142, 16.036699999999996, 16.055, 16.0708, 16.0858, 16.099999999999998, 16.1147, 16.1316, 16.150999999999996, 16.171599999999998, 16.192899999999998, 16.214899999999997, 16.238599999999998, 16.263399999999997, 16.2901, 16.3163, 16.3401, 16.362699999999997, 16.385499999999997, 16.4121, 16.4976, 16.542299999999997, 16.615899999999996, 16.9041, 18.5982], 'BNC1High': [17.406499999999998, 18.4564, 18.656399999999998, 19.5231, 19.639799999999997, 21.323, 21.573, 24.0396, 25.3395, 26.356099999999998, 28.3894, 29.422599999999996, 30.8226, 30.9559, 31.022599999999997, 31.7226, 31.822499999999998, 31.939100000000003, 32.5556, 33.422599999999996, 33.939, 34.0391, 34.1224, 34.2891, 35.2105, 36.522299999999994, 37.1889, 37.2387, 37.2724, 37.3222, 37.4056, 37.4723, 37.8723, 38.238899999999994, 38.3722, 38.4723, 38.5723, 39.4222, 40.0555, 40.9388, 42.3555, 42.522, 42.7554, 43.672000000000004, 46.5053, 49.321799999999996, 49.4718, 49.571799999999996], 'RotaryEncoder1_3': [33.9907], 'RotaryEncoder1_2': [49.5787]}}  # noqa
    error_trial = {'Bpod start timestamp': 0.0, 'Trial start timestamp': 0.0, 'Trial end timestamp': 15.485902, 'States timestamps': {'trial_start': [[0.0, 0.00010000000000021103]], 'reset_rotary_encoder': [[0.00010000000000021103, 0.00019999999999997797], [0.4855999999999998, 0.4857], [0.5165000000000002, 0.5166], [0.5331999999999999, 0.5333000000000001], [0.5461999999999998, 0.5463], [0.5590999999999999, 0.5592000000000001], [0.5741, 0.5742000000000003], [0.5952999999999999, 0.5954000000000002]], 'quiescent_period': [[0.00019999999999997797, 0.4855999999999998], [0.4857, 0.5165000000000002], [0.5166, 0.5331999999999999], [0.5333000000000001, 0.5461999999999998], [0.5463, 0.5590999999999999], [0.5592000000000001, 0.5741], [0.5742000000000003, 0.5952999999999999], [0.5954000000000002, 1.1006]], 'stim_on': [[1.1006, 1.2006000000000006]], 'reset2_rotary_encoder': [[1.2006000000000006, 1.2007000000000003]], 'closed_loop': [[1.2007000000000003, 13.4859]], 'error': [[13.4859, 15.4859]], 'no_go': [[np.nan, np.nan]], 'reward': [[np.nan, np.nan]], 'correct': [[np.nan, np.nan]]}, 'Events timestamps': {'Tup': [0.00010000000000021103, 0.00019999999999997797, 0.4857, 0.5166, 0.5333000000000001, 0.5463, 0.5592000000000001, 0.5742000000000003, 0.5954000000000002, 1.1006, 1.2006000000000006, 1.2007000000000003, 15.4859], 'BNC1High': [0.07390000000000008, 1.3236999999999997, 1.7572, 2.5072, 5.1071, 10.1735, 10.273399999999999, 10.3065, 10.8901, 11.023399999999999, 11.64, 11.739999999999998, 11.9068, 12.04, 12.3067, 12.6066, 12.773399999999999, 12.940000000000001, 13.3734, 13.423300000000001, 13.523399999999999], 'RotaryEncoder1_4': [0.4855999999999998, 0.5165000000000002, 0.5331999999999999, 0.5461999999999998, 0.5590999999999999, 0.5741, 0.5952999999999999, 1.7535999999999996], 'BNC1Low': [1.1719, 1.5057, 1.8071000000000002, 3.6715, 9.321200000000001, 10.2713, 10.304300000000001, 10.822600000000001, 10.938099999999999, 11.0551, 11.7211, 11.822099999999999, 12.023399999999999, 12.188400000000001, 12.3885, 12.6557, 12.8888, 13.1539, 13.405999999999999, 13.4541], 'RotaryEncoder1_3': [1.1886, 11.780000000000001], 'RotaryEncoder1_1': [13.4859]}}  # noqa
    no_go_trial = {'Bpod start timestamp': 0.0, 'Trial start timestamp': 2950.106299, 'Trial end timestamp': 3012.791701, 'States timestamps': {'trial_start': [[2950.106299, 2950.1063990000002]], 'reset_rotary_encoder': [[2950.1063990000002, 2950.106499], [2950.120499, 2950.120599], [2950.139099, 2950.139199], [2950.161899, 2950.161999], [2950.194099, 2950.194199]], 'quiescent_period': [[2950.106499, 2950.120499], [2950.120599, 2950.139099], [2950.139199, 2950.161899], [2950.161999, 2950.194099], [2950.194199, 2950.691599]], 'stim_on': [[2950.691599, 2950.791599]], 'reset2_rotary_encoder': [[2950.791599, 2950.791699]], 'closed_loop': [[2950.791699, 3010.791699]], 'no_go': [[3010.791699, 3012.791699]], 'error': [[np.nan, np.nan]], 'reward': [[np.nan, np.nan]], 'correct': [[np.nan, np.nan]]}, 'Events timestamps': {'Tup': [2950.1063990000002, 2950.106499, 2950.120599, 2950.139199, 2950.161999, 2950.194199, 2950.691599, 2950.791599, 2950.791699, 3010.791699, 3012.791699], 'RotaryEncoder1_3': [2950.120499, 2950.139099, 2950.161899, 2950.194099, 2981.703499], 'BNC1Low': [2950.181299, 2950.8635990000002, 2960.946299, 2961.162399, 2961.262399, 2976.078899, 2981.678699, 2981.761199, 2981.828799, 2981.862799, 2981.928699, 2982.0121990000002, 2995.844699, 2996.912299, 2997.028199, 2997.161899, 2997.311999, 2997.978999, 3005.278699, 3005.427699, 3005.4786990000002, 3005.610799, 3005.927599, 3011.129099, 3011.178199, 3011.245099], 'BNC1High': [2950.750499, 2960.766799, 2960.983499, 2961.183399, 2975.849599, 2981.549399, 2981.715999, 2981.799199, 2981.832599, 2981.899299, 2981.965999, 2982.099399, 2995.865499, 2996.9152990000002, 2997.082199, 2997.215499, 2997.415399, 3005.2484990000003, 3005.365199, 3005.448499, 3005.515099, 3005.881899, 3006.065199, 3011.148299, 3011.181399], 'RotaryEncoder1_4': [2961.126499], 'RotaryEncoder1_1': [3011.1679990000002]}}  # noqa
    # f = open(sph.DATA_FILE_PATH, 'a')
    next_trial_times = []
    trial_completed_times = []

    f, axes = op.make_fig(sph)
    plt.pause(1)

    for x in range(1000):
        t = time.time()
        tph.next_trial()
        next_trial_times.append(time.time() - t)
        # print('next_trial took: ', next_trial_times[-1], '(s)')
        t = time.time()
        tph = tph.trial_completed(np.random.choice(
            [correct_trial, error_trial, no_go_trial], p=[0.9, 0.05, 0.05]))

        if not x % 50:
            op.update_fig(f, axes, tph)
        # op.update_fig(f, axes, tph)

        tph.show_trial_log()

        trial_completed_times.append(time.time() - t)
        print('\nBLOCK NUM: {:>16}'.format(tph.block_num))
        print('BLOCK TRIAL NUM: {:>10s}'.format(
            f'{tph.block_trial_num}/{tph.block_len}'))
        print('PROBABILITY_LEFT: {:>9}'.format(tph.stim_probability_left))
        print('SIGNED CONTRAST: {:>10}'.format(tph.signed_contrast))

        if x == 90:
            print('break')
    op.update_fig(f, axes, tph)

    print('\nAverage next_trial times:', sum(next_trial_times) /
          len(next_trial_times))
    print('Average trial_completed times:', sum(trial_completed_times) /
          len(trial_completed_times))

    print('\n\n')
