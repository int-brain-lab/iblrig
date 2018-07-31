# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 14:06:34
# @Last Modified by:   N
# @Last Modified time: 2018-03-06 11:06:37
import random
import numpy as np
import scipy.stats as st
import copy
import json
import os


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


class staircase_contrast(object):
    """staircase_contrast trials happen with a frequency of self.freq, they
    define the contrast by counting the number of consecutive hits and misses
    and adjust the contrast difficulty by adjusting the step of the contrasts.
    `self.contrasts` -> [1., 0.5, 0.25, 0.125, 0.0625, 0.]
    `self.step`      ->  0^  1^   2^    3^     4^      5^

    `self.step` is the pointer of `self.contrasts` that correspond to the
    current contrast in use. To get the current contrast,
    `self.contrast` can be called to return the current contrast by calling:
    `self.contrasts[self.step]`

    For each `self.hit_thresh` consecutive hits `self.step` increases
    For each `self.miss_thresh` consecutive misses `self.step` decreases
    Every time a threshold is crossed counters are reset.
    """
    def __init__(self, sph):
        self.type = 'staircase_contrast'
        self.ntrials = 0
        self.contrasts = sph.STIM_CONTRASTS
        self.step = 0
        self.freq = sph.ST_FREQ
        self.hits = 0
        self.misses = 0
        self.hit_thresh = sph.ST_HIT_THRESH
        self.miss_thresh = sph.ST_MISS_THRESH
        self.trial_correct = None

    def reprJSON(self):
        d = self.__dict__
        c = {'contrast': self.contrast}
        d.update(c)
        return d  # "\n\n    " + str(d) + "\n\n"

    def _reset_counters(self):
        self.hits = 0
        self.misses = 0
        return

    def _update_step(self):
        if self.hits >= self.hit_thresh:
            self.step = self.step + 1
            self._reset_counters()
        if self.misses >= self.miss_thresh:
            self.step -= 1
            self._reset_counters()
        # self.step is bound by the available contrasts
        if self.step > len(self.contrasts) - 1:
            self.step = len(self.contrasts) - 1
        elif self.step < 0:
            self.step = 0
        return

    @property
    def contrast(self):
        """staircase_contrast trial current contrast:"""
        return self.contrasts[self.step]

    def trial_completed(self, trial_correct):
        self.ntrials += 1
        self.trial_correct = trial_correct

    def next_trial(self):
        """Updates obj with behavioral outcome from trial.trial_completed
        and calculates next contrast"""
        if self.trial_correct:
            self.hits += 1
        elif not self.trial_correct:
            self.misses += 1
        self._update_step()
        self.trial_correct = None
        return


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
        self.buffer_size = sph.AT_BUFFER_SIZE
        self.ntrials = 0
        self.trial_125 = 0
        self.previous_session = sph.PREVIOUS_DATA_FILE
        self.last_trial_data = self._load_last_trial_data()
        self.contrasts = self._init_contrasts()
        self.buffer = self._init_buffer()

        self.contrast = self._init_contrast()
        self.trial_correct = None

        self.last_trial_data = None

    def reprJSON(self):
        return self.__dict__

    def _load_last_trial_data(self):
        if (self.previous_session is None or
                os.stat(self.previous_session).st_size == 0):
            print('###################################')
            print('## WARNING: USING DEFAULT VALUES ##')
            print('###################################')
            print('  [no previous session was found]  ')
            return
        else:
            trial_data = []
            with open(self.previous_session, 'r') as f:
                for line in f:
                    last_trial = json.loads(line)
                    trial_data.append(last_trial)
            return trial_data[-1]

    def _init_contrasts(self):
        if self.previous_session is None or not self.last_trial_data:
            _contrasts = [1., 0.5]
        else:
            _contrasts = self.last_trial_data['ac']['contrasts']
            pass
        return _contrasts

    def _init_buffer(self):
        if self.previous_session is None or not self.last_trial_data:
            _buffer = np.zeros(self.buffer_size).tolist()
        else:
            _buffer = self.last_trial_data['ac']['buffer']
        return _buffer

    def _init_contrast(self):
        _contrast = random.choice(self.contrasts)
        return _contrast

    def _reset_buffer(self):
        self.buffer = np.zeros(self.buffer_size).tolist()

    def _update_buffer(self):
        _buffer = self.buffer[1:].copy()
        _buffer.append(int(self.trial_correct))
        self.buffer = _buffer

    def _update_contrast(self):
        self.contrast = random.choice(self.contrasts)

    def _update_contrasts(self):  # can be done better!
        if self.ntrials - self.trial_125 == 500:
            self.contrasts.append(0.)

        if len(self.contrasts) == 2:
            if sum(self.buffer) >= self._min_trials_at(0.7, 0.05):
                self.contrasts.append(0.25)
                self._reset_buffer()
        elif len(self.contrasts) == 3:
            if sum(self.buffer) >= self._min_trials_at(0.5, 0.05):
                self.contrasts.append(0.125)
                self.trial_125 = self.ntrials
                self._reset_buffer()
        elif len(self.contrasts) == 4:
            if sum(self.buffer) >= self._min_trials_at(0.5, 0.05):
                self.contrasts.append(0.0625)
                self._reset_buffer()
        elif len(self.contrasts) == 5:
            if sum(self.buffer) >= self._min_trials_at(0.5, 0.05):
                if 0. not in self.contrasts:
                    self.contrasts.append(0.)
                elif 0. in self.contrasts:
                    self.contrasts.append(0.0625)
                self._reset_buffer()

    def _min_trials_at(self, prob, alpha):
        return sum(1 - st.binom.cdf(range(self.buffer_size),
                   self.buffer_size, prob) >= alpha)

    def trial_completed(self, trial_correct):
        self.ntrials += 1
        self.trial_correct = trial_correct

    def next_trial(self):
        """Updates obj with behavioral outcome from trial.trial_completed
        and calculates next contrast"""
        self._update_buffer()
        self._update_contrasts()
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
        c = {'contrast': self.contrast}
        d.update(c)
        return d  # "\n\n    " + str(d) + "\n\n"

    @property
    def contrast(self):
        return self._contrast

    @contrast.setter
    def contrast(self, previous_contrast):
        self._contrast = previous_contrast

    def trial_completed(self, trial_correct):
        self.ntrials += 1
        self.trial_correct = trial_correct

    def next_trial(self):
        """Updates obj with behavioral outcome from trial.trial_completed
        and keeps contrast in case of mistake and sets contrast to None in
        case of correct trial -> exits from repeat trials"""
        if self.trial_correct:
            self.contrast = None
        else:
            self.contrast = self.contrast
        self.trial_correct = None


class trial_param_handler(object):
    """All trial parameters for the current trial.
    On self.trial_completed a JSON serializable string containing state/event
    data and all the parameters is returned to be printed out and saved by
    pybpod under the stdout flag.
    self.next_trial calls the update functions of all related objects
    """
    def __init__(self, sph):
        # Constants from settings
        self.data_file_path = sph.DATA_FILE_PATH
        self.data_file = open(self.data_file_path, 'a')
        self.positions = sph.STIM_POSITIONS
        self.contrasts = sph.STIM_CONTRASTS
        self.repeat_on_error = sph.REPEAT_ON_ERROR
        self.repeat_stims = sph.REPEAT_STIMS
        self.threshold_events_dict = sph.THRESHOLD_EVENTS
        self.quiescent_period = sph.QUIESCENT_PERIOD
        self.response_window = sph.RESPONSE_WINDOW
        self.interactive_delay = sph.INTERACTIVE_DELAY
        self.iti_correct = sph.ITI_CORRECT - sph.VALVE_TIME
        self.iti_error = sph.ITI_ERROR
        self.reward_valve_time = sph.VALVE_TIME
        # Init trial type objects
        self.ac = adaptive_contrast(sph)
        self.sc = staircase_contrast(sph)
        self.rc = repeat_contrast()
        # Dynamic params (Change every trial)
        self.trial_num = 0
        self.position = random.choice(sph.STIM_POSITIONS)
        self.event_error = sph.THRESHOLD_EVENTS[self.position]
        self.event_reward = sph.THRESHOLD_EVENTS[-self.position]
        self.movement_left = sph.THRESHOLD_EVENTS[sph.QUIESCENCE_THRESHOLDS[0]]
        self.movement_right = sph.THRESHOLD_EVENTS[sph.QUIESCENCE_THRESHOLDS[1]
                                                   ]
        # Performance related params that depend on trial outcome
        self.trial = self.ac
        self.contrast = self.trial.contrast
        # Outcome parameters that depend on mouse behavior
        self.trial_correct = None
        self.ntrials_correct = 0
        self._previous_trial = None

    def reprJSON(self):
        return self.__dict__

    def trial_completed(self, behavior_data):
        """Update outcome variables using bpod.session.current_trial
        Check trial for state entries, first value of first tuple"""
        correct = ~np.isnan(
            behavior_data['States timestamps']['correct'][0][0])
        error = ~np.isnan(
            behavior_data['States timestamps']['error'][0][0])
        assert correct is not error
        self.trial_correct = bool(correct)
        self.ntrials_correct += self.trial_correct

        self.trial.trial_completed(self.trial_correct)

        params = self.__dict__.copy()
        params.update({'behavior_data': behavior_data})
        # open data_file is not serializable, convert to str
        params['data_file'] = str(params['data_file'])

        out = json.dumps(params, cls=ComplexEncoder)
        self.data_file.write(out)
        self.data_file.write('\n')
        self.data_file.close()
        return json.loads(out)

    def next_trial(self):
        # First trial exception
        if self.trial_num == 0:
            self.trial_num += 1
            return
        self.data_file = str(self.data_file)
        # Backup previous vars before changing them
        self._previous_trial = copy.deepcopy(self)
        # increment trial number
        self.trial_num += 1
        # update + next contrast: update buffers/counters + get next contrast
        # This has to happen before self.trial is changed to the next trial
        self.trial.next_trial()
        # Update staircase available contrasts
        self.sc.contrasts = self.ac.contrasts
        # update dynamic vars (position and events)
        self._next_dynamic_vars()
        # update vars dependent on trial outcome trial and contrast
        self._next_performance_vars()
        # Reset outcome variables for next trial
        self.trial_correct = None
        # Remove backup of previous trial
        self._previous_trial = None
        # Open the data file to append the next trial
        self.data_file = open(self.data_file_path, 'a')

    def _next_dynamic_vars(self):
        if not self.trial_correct and self.repeat_on_error:
            self.position = self.position
            self.event_error = self.threshold_events_dict[self.position]
            self.event_reward = self.threshold_events_dict[-self.position]
        else:
            self.position = random.choice(self.positions)
            self.event_error = self.threshold_events_dict[self.position]
            self.event_reward = self.threshold_events_dict[-self.position]
        return

    def _next_performance_vars(self):
        non_rc_ntrials = self.trial_num - self.rc.ntrials
        if self.trial_correct is None:
            print('Trial is either not finished or no data was passed')
        elif self.trial_correct or not self.repeat_on_error:
            self.trial = self.ac if non_rc_ntrials % self.sc.freq else self.sc
        elif (self.contrast in self.repeat_stims and self.repeat_on_error and
              not self.trial_correct):
            self.trial = self.rc
            self.trial.contrast = self.contrast

        self.contrast = self.trial.contrast
        return

    def send_current_trial_info(self, osc_client=None, trial_num=0.,
                                t_position=0., t_contrast=1., t_freq=10.,
                                t_angle=90., t_gain=1., t_sigma=30.):
        """
        Sends all info relevant for stim production to Bonsai using OSC
        OSC channels:
            USED:
            /t  -> (int)    trial number current
            /p  -> (int)    position of stimulus init for current trial
            /c  -> (float)  contrast of stimulus for current trial
            /f  -> (float)  frequency of gabor patch for current trial
            /a  -> (float)  angle of gabor patch for current trial
            /g  -> (float)  gain of RE to visual stim displacement
            /s  -> (float)  sigma of the 2D gaussian of gabor
            /e  -> (int)    events transitions  USED BY SOFTCODE HANDLER FUNC
        """
        if osc_client is None:
            print('Can''t send message without an OSC client: client is None')
        t_position = t_position  # (2/3)*t_position/180
        osc_client.send_message("/t", trial_num)
        osc_client.send_message("/p", t_position)
        osc_client.send_message("/c", t_contrast)
        osc_client.send_message("/f", t_freq)
        osc_client.send_message("/a", t_angle)
        osc_client.send_message("/g", t_gain)
        osc_client.send_message("/s", t_sigma)


if __name__ == '__main__':

    from session_params import session_param_handler
    import task_settings
    sph = session_param_handler(task_settings)
    tph = trial_param_handler(sph)
    ac = adaptive_contrast(sph)
    sc = staircase_contrast(sph)
    rc = repeat_contrast()
    correct_trial = {'Events timestamps': {'GlobalTimer1_End': [10.0],
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
                     'States timestamps': {'error': [(np.nan, np.nan)],
                                           'correct': [(0.0001, 10.0)],
                                           'TimerTrig': [(0, 0.0001)],
                                           'Port3Active1': [(np.nan,
                                                             np.nan)]
                                           }
                     }

    error_trial = {'Events timestamps': {'GlobalTimer1_End': [10.0],
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
                   'States timestamps': {'correct': [(np.nan, np.nan)],
                                         'error': [(0.0001, 10.0)],
                                         'TimerTrig': [(0, 0.0001)],
                                         'Port3Active1': [(np.nan,
                                                           np.nan)]
                                         }
                   }

    import time
    # f = open(sph.DATA_FILE_PATH, 'a')
    next_trial_times = []
    trial_completed_times = []
    for x in range(500):

        t = time.time()
        tph.next_trial()
        next_trial_times.append(time.time() - t)
        print('next_trial took: ', next_trial_times[-1], '(s)')
        t = time.time()
        data = tph.trial_completed(random.choice([correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 correct_trial, correct_trial,
                                                 error_trial, error_trial,
                                                 error_trial, error_trial,
                                                  ]))
        trial_completed_times.append(time.time() - t)
        print('trial_completed took: ', trial_completed_times[-1], '(s)')
        print('\n\n')

    print('Average next_trial times:', sum(next_trial_times) /
          len(next_trial_times))
    print('Average trial_completed times:', sum(trial_completed_times) /
          len(trial_completed_times))

    # print('\n\n')
    # trial_data = []
    # with open(sph.DATA_FILE_PATH, 'r') as f:
    #     for line in f:
    #         last_trial = json.loads(line)
    #         trial_data.append(last_trial)
    # print(last_trial)
