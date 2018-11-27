# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 14:06:34
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-06-26 17:36:59
import random
import numpy as np
import scipy.stats as st
import json
import os
from dateutil import parser
import math


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


class adaptive_contrast(object):
    """Adaptive contrast trials happen whenever staircase contrasts do not.
    In any particular trial a contrast is drawn from a self.contrasts pool
    pseudo-randomly. This pool is loaded from the last trial of the previous
    session (in data['ac']['contrasts']). If previous session is inexistant
    contrast pool is initialized with [1., 0.5].
    The number of correct trials in a buffer of self.buffer_size is calculated
    and compared to a binomial distribution with alpha = 0.05 at differnt
    probabilities (self._update_contrasts). if enough correct trials are
    achieved the contrasts pool is increased. Similiarly to the contrasts pool
    the buffer is also loaded from the previous session (data['ac']['buffer'])
    every time a contrast value is added to the contrasts pool the buffer is
    reset.
    """

    def __init__(self, sph):
        self.type = 'adaptive_contrast'
        self.all_contrasts = sph.CONTRAST_SET
        self.init_contrasts = sph.AC_INIT_CONTRASTS
        self.buffer_size = sph.AC_BUFFER_SIZE
        self.perf_crit_one = self._min_trials_at(sph.AC_PERF_CRIT_ONE, 0.05)
        self.perf_crit_two = self._min_trials_at(sph.AC_PERF_CRIT_TWO, 0.05)
        self.ntrials_to_zero = sph.AC_NTRIALS_TO_ZERO
        self.ntrials = 0
        self.ntrials_125 = 0
        self.previous_session = sph.PREVIOUS_DATA_FILE
        self.last_trial_data = self._load_last_trial_data(sph.LAST_TRIAL_DATA)

        self.contrast_set = self._init_contrast_set()
        self.buffer = self._init_buffer()

        self.value = self._init_contrast()
        self.trial_correct = None
        self.signed_contrast = None

        self.last_trial_data = None

    def reprJSON(self):
        return self.__dict__

    def _load_last_trial_data(self, sph_last_trial_data):
        if (self.previous_session is None or
                os.stat(self.previous_session).st_size == 0):
            print('###################################')
            print('## WARNING: USING DEFAULT VALUES ##')
            print('###################################')
            print('  [no previous session was found]  ')
            return
        else:
            return sph_last_trial_data

    def _init_contrast_set(self):
        if self.previous_session is None or not self.last_trial_data:
            _contrasts = self.init_contrasts
        else:
            _contrasts = self.last_trial_data['ac']['contrast_set']
        return _contrasts

    def _init_buffer(self):
        if self.previous_session is None or not self.last_trial_data:
            _buffer = np.zeros((2, self.buffer_size, len(self.all_contrasts))).tolist()
        else:
            _buffer = self.last_trial_data['ac']['buffer']
            if len(_buffer) > 2:
                _buffer = np.zeros((2, self.buffer_size, len(self.all_contrasts))).tolist()
        return _buffer

    def _init_contrast(self):
        _contrast = random.choice(self.contrast_set)
        return _contrast

    def _reset_buffer(self):
        self.buffer = np.zeros((2, self.buffer_size, len(self.all_contrasts))).tolist()

    def _update_buffer(self):
        _buffer = np.asarray(self.buffer)
        side_idx = 0 if self.signed_contrast < 0 else 1
        contrast_idx = self.contrast_set.index(self.value)
        col = _buffer[side_idx, :, contrast_idx]
        col = np.roll(col, -1)
        col[-1] = int(self.trial_correct)
        _buffer[side_idx, :, contrast_idx] = col
        self.buffer = _buffer.tolist()

    def _update_contrast(self):
        self.value = random.choice(self.contrast_set)

    def _update_contrast_set(self):
        curr_idx = np.array([True if x in self.contrast_set else False for x in self.all_contrasts])
        min_idx = sum(curr_idx[:-1]) - 1
        new_idx = np.array([False for x in self.all_contrasts])
        # Update counter of how mant trials were performend with 0.125 contrast
        if 0.125 in self.contrast_set:
            self.ntrials_125 += 1
        # Add zero contrast if ntrials after introducing 0.125 have elapsed
        if self.ntrials_125 >= self.ntrials_to_zero:
            new_idx[-1] = True
        # Sum correct left AND right trials for all contrasts
        _ntrials = np.sum(self.buffer, axis=1)
        # Define crit for next contrast insert
        if 0.125 in self.contrast_set:
            pass_crit = _ntrials > self.perf_crit_two
        else:
            pass_crit = _ntrials > self.perf_crit_one
        # Check if both left AND right have passed criterion
        pass_idx = np.bitwise_and(pass_crit[0], pass_crit[1])
        # If lowest contrast passes add new contrast
        if pass_idx[min_idx]:
            new_idx[min_idx + 1] = True
        # Make new_idx
        new_idx = new_idx | curr_idx | pass_idx

        # Finally update the contrast_set
        self.contrast_set = np.asarray(self.all_contrasts)[new_idx].tolist()

    def _min_trials_at(self, prob, alpha):
        return int(sum(1 - st.binom.cdf(range(self.buffer_size),
                   self.buffer_size, prob) >= alpha))

    def trial_completed(self, trial_correct, signed_contrast):
        self.ntrials += 1
        self.trial_correct = trial_correct
        self.signed_contrast = signed_contrast

    def next_trial(self):
        """Updates obj with behavioral outcome from trial.trial_completed
        and calculates next contrast"""
        self._update_buffer()
        self._update_contrast_set()
        self._update_contrast()
        self.trial_correct = None


class repeat_contrast(object):
    """Dummy trial object will count repeat trials and reset contrast to none
    if trial correct"""
    def __init__(self):
        self.type = 'repeat_contrast'
        self.ntrials = 0
        self._contrast = None
        self.trial_correct = None
        # add if not correct contrast don't repeat

    def reprJSON(self):
        d = self.__dict__
        c = {'value': self.value}
        d.update(c)
        return d  # "\n\n    " + str(d) + "\n\n"

    @property
    def value(self):
        return self._contrast

    @value.setter
    def value(self, previous_contrast):
        self._contrast = previous_contrast

    def trial_completed(self, trial_correct, signed_contrast):
        self.ntrials += 1
        self.trial_correct = trial_correct

    def next_trial(self):
        """Updates obj with behavioral outcome from trial.trial_completed
        and keeps contrast in case of mistake and sets contrast to None in
        case of correct trial -> exits from repeat trials"""
        if self.trial_correct:
            self.value = None
        else:
            self.value = self.value
        self.trial_correct = None


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
        self.data_file_path = sph.DATA_FILE_PATH
        self.data_file = open(self.data_file_path, 'a')
        self.position_set = sph.STIM_POSITIONS
        self.contrast_set = sph.CONTRAST_SET
        self.repeat_on_error = sph.REPEAT_ON_ERROR
        self.repeat_contrasts = sph.REPEAT_CONTRASTS
        self.threshold_events_dict = sph.THRESHOLD_EVENTS
        self.quiescent_period = sph.QUIESCENT_PERIOD
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
        # Reward amount
        self.reward_calibration = sph.CALIBRATION_VALUE
        self.reward_amount = sph.REWARD_AMOUNT
        self.reward_valve_time = self.reward_amount * self.reward_calibration
        self.iti_correct = self.iti_correct_target - self.reward_valve_time
        # Init trial type objects
        self.ac = adaptive_contrast(sph)
        self.rc = repeat_contrast()
        # Initialize parameters that may change every trial
        self.trial_num = 0
        self.non_rc_ntrials = self.trial_num - self.rc.ntrials
        self.position = random.choice(sph.STIM_POSITIONS)
        self.stim_probability_left = sph.STIM_PROBABILITY_LEFT
        self.stim_phase = 0.
        self.event_error = sph.THRESHOLD_EVENTS[self.position]
        self.event_reward = sph.THRESHOLD_EVENTS[-self.position]
        self.movement_left = sph.THRESHOLD_EVENTS[sph.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = sph.THRESHOLD_EVENTS[sph.QUIESCENCE_THRESHOLDS[1]]
        self.response_buffer = [0] * sph.RESPONSE_BUFFER_LENGTH
        # Outcome related parmeters
        self.contrast = self.ac
        self.current_contrast = self.contrast.value
        self.signed_contrast = self.contrast.value * np.sign(self.position)
        self.trial_correct = None
        self.ntrials_correct = 0
        self.water_delivered = 0

    def reprJSON(self):
        return self.__dict__

    def trial_completed(self, behavior_data):
        """Update outcome variables using bpod.session.current_trial
        Check trial for state entries, first value of first tuple"""
        correct = ~np.isnan(
            behavior_data['States timestamps']['correct'][0][0])
        error = ~np.isnan(
            behavior_data['States timestamps']['error'][0][0])
        no_go = ~np.isnan(
            behavior_data['States timestamps']['no_go'][0][0])
        assert correct or error or no_go
        # Update response buffer -1 for left, 0 for nogo, and 1 for rightward
        if (correct and self.position < 0) or (error and self.position > 0):
            self._update_response_buffer(1)
        elif (correct and self.position > 0) or (error and self.position < 0):
            self._update_response_buffer(-1)
        elif no_go:
            self._update_response_buffer(0)
        # Update the trial_correct variable
        self.trial_correct = bool(correct)
        # Increment the trial correct counter
        self.ntrials_correct += self.trial_correct
        # Update the water delivered
        if self.trial_correct:
            self.water_delivered = self.water_delivered + self.reward_amount
        # Propagate outcome to contrast object
        self.contrast.trial_completed(self.trial_correct, self.signed_contrast)
        #SAVE TRIAL DATA
        params = self.__dict__.copy()
        params.update({'behavior_data': behavior_data})
        # open data_file is not serializable, convert to str
        params['data_file'] = str(params['data_file'])
        params['osc_client'] = 'osc_client_pointer'
        params['init_datetime'] = params['init_datetime'].isoformat()

        out = json.dumps(params, cls=ComplexEncoder)
        self.data_file.write(out)
        self.data_file.write('\n')
        self.data_file.close()
        return json.loads(out)

    def next_trial(self):
        # First trial exception
        if self.trial_num == 0:
            self.trial_num += 1
            # Send next trial info to Bonsai
            self.send_current_trial_info()
            return
        self.data_file = str(self.data_file)
        # update + next contrast: update buffers/counters + get next contrast
        # This has to happen before self.contrast is pointing to next trials
        self.contrast.next_trial()
        # Increment trial number
        self.trial_num += 1
        # Update non repeated trials
        self.non_rc_ntrials = self.trial_num - self.rc.ntrials
        # Update stimulus phase
        self.stim_phase = random.uniform(0, math.pi)
        # Update contrast
        self._next_contrast()
        # Update position
        self.position = self._next_position()
        # Update state machine events
        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
        # Reset outcome variables for next trial
        self.trial_correct = None
        # Open the data file to append the next trial
        self.data_file = open(self.data_file_path, 'a')
        # Send next trial info to Bonsai
        self.send_current_trial_info()

    def _update_response_buffer(self, val):
        _buffer = self.response_buffer
        _buffer = np.roll(_buffer, -1, axis=0)
        _buffer[-1] = val
        self.response_buffer = _buffer.tolist()
        return _buffer

    def _next_contrast(self):        # Decide which case we are in
        if self.trial_correct:
            # Case correct trial
            case = '1**'
        elif not self.trial_correct and not self.repeat_on_error:
            # Case incorrect trial, no_repeat
            case = '00*'
        elif (not self.trial_correct and self.repeat_on_error and
              self.contrast.value not in self.repeat_contrasts):
            # Case incorrect, repeat on error, NON repeatable contrast
            case = '010'
        elif (not self.trial_correct and self.repeat_on_error and
              self.contrast.value in self.repeat_contrasts):
            # Case incorrect, repeat on error, repeatable contrast
            case = '011'

        # Set next contrast
        if case == '011':
            self.contrast = self.rc
            self.contrast.value = self.current_contrast
        else:  # if case == '1**' or case == '00*' or case == '010':
            self.contrast = self.ac

        self.current_contrast = self.contrast.value
        self.signed_contrast = self.contrast.value * np.sign(self.position)
        return

    def _next_position(self):
        if self.contrast.type == 'repeat_contrast':
            rightward_responses = [int(x) for x in self.response_buffer if x == 1]
            right_proportion = sum(rightward_responses) / len(self.response_buffer)
            if random.gauss(right_proportion, 0.5) < 0.5:
                _position = -35  # show the stim on the left
            else:
                _position = 35
            print("repeat_contrast, bias position:", _position)
            return _position
        else:
            _position = np.random.choice(self.position_set,
                                         p=[self.stim_probability_left,
                                            1 - self.stim_probability_left])
        return int(_position)

    def send_current_trial_info(self):
        """
        Sends all info relevant for stim production to Bonsai using OSC
        OSC channels:
            USED:
            /t  -> (int)    trial number current
            /p  -> (int)    position of stimulus init for current trial
            /h  -> (float)  phase of gabor for current trial
            /c  -> (float)  contrast of stimulus for current trial
            /f  -> (float)  frequency of gabor patch for current trial
            /a  -> (float)  angle of gabor patch for current trial
            /g  -> (float)  gain of RE to visual stim displacement
            /s  -> (float)  sigma of the 2D gaussian of gabor
            /e  -> (int)    events transitions  USED BY SOFTCODE HANDLER FUNC
        """
        if self.osc_client is None:
            print('Can''t send message without an OSC client: client is None')
        # self.position = self.position  # (2/3)*t_position/180
        self.osc_client.send_message("/t", self.trial_num)
        self.osc_client.send_message("/p", self.position)
        self.osc_client.send_message("/h", self.stim_phase)
        self.osc_client.send_message("/c", self.contrast.value)
        self.osc_client.send_message("/f", self.stim_freq)
        self.osc_client.send_message("/a", self.stim_angle)
        self.osc_client.send_message("/g", self.stim_gain)
        self.osc_client.send_message("/s", self.stim_sigma)


if __name__ == '__main__':

    from session_params import SessionParamHandler
    import time
    import task_settings as _task_settings
    import _user_settings
    sph = SessionParamHandler(_task_settings, _user_settings)
    tph = TrialParamHandler(sph)
    ac = adaptive_contrast(sph)
    rc = repeat_contrast()
    correct_trial = {'Trial end timestamp': 5.1234,
                     'Trial start timestamp': 1.1234,
                     'Events timestamps': {'GlobalTimer1_End': [10.0],
                                           'Port2In': [2.2133, 3.6032,
                                                       4.1014, 4.7648,
                                                       5.1329, 5.6429,
                                                       6.4632, 6.5842,
                                                       6.8691, 7.1565,
                                                       7.6357, 7.8717,
                                                       8.1396, 8.4102],
                                           'Tup': [0.0001],
                                           'Port3In': [9.5196],
                                           'Port2Out': [2.3768, 3.9778,
                                                        4.4069, 5.0538,
                                                        5.3777, 5.8241,
                                                        6.472, 6.7757,
                                                        7.0552, 7.543,
                                                        7.7867, 8.0342,
                                                        8.273, 8.5793]
                                           },
                     'Bpod start timestamp': 0.117,
                     'States timestamps': {'no_go': [(np.nan, np.nan)],
                                           'error': [(np.nan, np.nan)],
                                           'correct': [(0.0001, 10.0)],
                                           'TimerTrig': [(0, 0.0001)],
                                           'Port3Active1': [(np.nan,
                                                             np.nan)]
                                           }
                     }
    error_trial = {'Trial start timestamp': 1.1234,
                   'Trial end timestamp': 5.1234,
                   'Events timestamps': {'GlobalTimer1_End': [10.0],
                                         'Port2In': [2.2133, 3.6032,
                                                     4.1014, 4.7648,
                                                     5.1329, 5.6429,
                                                     6.4632, 6.5842,
                                                     6.8691, 7.1565,
                                                     7.6357, 7.8717,
                                                     8.1396, 8.4102],
                                         'Tup': [0.0001],
                                         'Port3In': [9.5196],
                                         'Port2Out': [2.3768, 3.9778,
                                                      4.4069, 5.0538,
                                                      5.3777, 5.8241,
                                                      6.472, 6.7757,
                                                      7.0552, 7.543,
                                                      7.7867, 8.0342,
                                                      8.273, 8.5793]
                                         },
                   'Bpod start timestamp': 0.117,
                   'States timestamps': {'no_go': [(np.nan, np.nan)],
                                         'correct': [(np.nan, np.nan)],
                                         'error': [(0.0001, 10.0)],
                                         'TimerTrig': [(0, 0.0001)],
                                         'Port3Active1': [(np.nan,
                                                           np.nan)]
                                         }
                   }
    no_go_trial = {'Trial start timestamp': 1.1234,
                   'Trial end timestamp': 5.1234,
                   'Events timestamps': {'GlobalTimer1_End': [10.0],
                                         'Port2In': [2.2133, 3.6032,
                                                     4.1014, 4.7648,
                                                     5.1329, 5.6429,
                                                     6.4632, 6.5842,
                                                     6.8691, 7.1565,
                                                     7.6357, 7.8717,
                                                     8.1396, 8.4102],
                                         'Tup': [0.0001],
                                         'Port3In': [9.5196],
                                         'Port2Out': [2.3768, 3.9778,
                                                      4.4069, 5.0538,
                                                      5.3777, 5.8241,
                                                      6.472, 6.7757,
                                                      7.0552, 7.543,
                                                      7.7867, 8.0342,
                                                      8.273, 8.5793]
                                         },
                   'Bpod start timestamp': 0.117,
                   'States timestamps': {'no_go': [(0.0001, 10.0)],
                                         'correct': [(np.nan, np.nan)],
                                         'error': [(np.nan, np.nan)],
                                         'TimerTrig': [(0, 0.0001)],
                                         'Port3Active1': [(np.nan,
                                                           np.nan)]
                                         }
                   }

    # f = open(sph.DATA_FILE_PATH, 'a')
    next_trial_times = []
    trial_completed_times = []
    for x in range(1000):
        t = time.time()
        tph.next_trial()
        next_trial_times.append(time.time() - t)
        # print('next_trial took: ', next_trial_times[-1], '(s)')
        t = time.time()
        data = tph.trial_completed(random.choice([correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                  correct_trial, correct_trial,
                                                  correct_trial, correct_trial,
                                                  error_trial, no_go_trial,
                                                  ]))
        trial_completed_times.append(time.time() - t)
        # print('trial_completed took: ', trial_completed_times[-1], '(s)')
        # print('\n\n')

    print('Average next_trial times:', sum(next_trial_times) /
          len(next_trial_times))
    print('Average trial_completed times:', sum(trial_completed_times) /
          len(trial_completed_times))

    from ibllib.io import raw_data_loaders as raw
    data = raw.load_data(sph.SESSION_FOLDER)
    print([x['ac']['contrast_set'] for x in data[-100:]])

    print('\n\n')
    # trial_data = []
    # with open(sph.DATA_FILE_PATH, 'r') as f:
    #     for line in f:
    #         last_trial = json.loads(line)
    #         trial_data.append(last_trial)
    # print(last_trial)
