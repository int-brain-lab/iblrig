# !/usr/bin/python3
# -*- coding: utf-8 -*-
import random
import numpy as np
import copy
import json


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


class trial_param_handler(object):
    """All trial parameters for the current trial.
    On self.trial_completed a JSON serializable string containing state/event
    data and all the parameters is returned to be printed out and saved by
    pybpod under the stdout flag.
    self.next_trial calls the update functions of all related objects
    """
    def __init__(self, sph):
        # Constants from settings
        self.data_dile_path = sph.DATA_FILE_PATH
        self.data_file = open(self.data_dile_path, 'a')
        self.positions = sph.STIM_POSITIONS
        self.contrasts = sph.STIM_CONTRASTS
        self.repeat_on_error = sph.REPEAT_ON_ERROR
        self.repeat_stims = sph.REPEAT_STIMS
        self.threshold_events_dict = sph.THRESHOLD_EVENTS
        self.response_window = sph.RESPONSE_WINDOW
        self.interactive_delay = sph.INTERACTIVE_DELAY
        self.iti = sph.ITI
        self.iti_correct = sph.ITI_CORRECT
        self.iti_error = sph.ITI_ERROR
        self.reward_valve_time = sph.VALVE_TIME
        # Dynamic params (Change every trial)
        self.trial_num = 0
        self.nrepeated_trials = 0
        self.is_reprat_trial = False
        self.position = random.choice(self.positions)
        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
        self._contrast = random.choice(self.contrasts)
        # Outcome parameters that depend on mouse behavior
        self.trial_correct = None
        self._previous_trial = None

    def reprJSON(self):
        return self.__dict__

    @property
    def contrast(self):
        return self._contrast

    @contrast.setter
    def contrast(self, value):
        self._contrast = value

    def trial_completed(self, behavior_data):
        """Update outcome variables using bpod.session.current_trial
        Check trial for state entries, first value of first tuple"""
        correct = ~np.isnan(
            behavior_data['States timestamps']['correct'][0][0])
        error = ~np.isnan(
            behavior_data['States timestamps']['error'][0][0])
        assert correct is not error
        self.trial_correct = bool(correct)

        params = self.__dict__.copy()
        params.update({'behavior_data': behavior_data})
        # open data_file is not serializable, convert to str
        params['data_file'] = str(params['data_file'])

        out = json.dumps(params, cls=ComplexEncoder)
        self.data_file.write(out)
        self.data_file.write('\n')
        self.data_file.close()
        return out

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
        # update dynamic vars (position and events)
        self._next_dynamic_vars()
        # Reset outcome variables for next trial
        self.trial_correct = None
        # Remove backup of previous trial
        self._previous_trial = None
        # Open the data file to append the next trial
        self.data_file = open(self.data_dile_path, 'a')

    def _next_dynamic_vars(self):
        if (self.repeat_on_error and
                self.contrast in self.repeat_stims and not self.trial_correct):
            self.contrast = self.contrast
            self.position = self.position
            self.nrepeated_trials += 1
            self.is_reprat_trial = True
        else:
            self.contrast = random.choice(self.contrasts)
            self.position = random.choice(self.positions)
            self.is_reprat_trial = False

        self.event_error = self.threshold_events_dict[self.position]
        self.event_reward = self.threshold_events_dict[-self.position]
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
            USED IN SOFTCODE FUNC:
            /e  -> (int)    events transitions  USED BY SOFTCODE HANDLER FUNC
        """
    #   [float(x) for x in ''.join([x.strip('()[]') for x in s]).split(',')]
    #   import ast; ast.literal_eval(s)

        # global client
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
    pass
    # from session_params import session_param_handler
    # import settings
    # sph = session_param_handler(settings)
    # tph = trial_param_handler(sph)
    # correct_trial = {'Events timestamps': {'GlobalTimer1_End': [10.0],
    #                                        'Port2In': [2.2133, 3.6032,
    #                                                    4.1014, 4.7648,
    #                                                    5.1329, 5.6429,
    #                                                    6.4632, 6.5842,
    #                                                    6.8691, 7.1565,
    #                                                    7.6357, 7.8717,
    #                                                    8.1396, 8.4102],
    #                                        'Tup': [0.0001],
    #                                        'Port3In': [9.5196],
    #                                        'Port2Out': [2.3768, 3.9778,
    #                                                     4.4069, 5.0538,
    #                                                     5.3777, 5.8241,
    #                                                     6.472, 6.7757,
    #                                                     7.0552, 7.543,
    #                                                     7.7867, 8.0342,
    #                                                     8.273, 8.5793]
    #                                        },
    #                  'Bpod start timestamp': 0.117,
    #                  'States timestamps': {'error': [(np.nan, np.nan)],
    #                                        'correct': [(0.0001, 10.0)],
    #                                        'TimerTrig': [(0, 0.0001)],
    #                                        'Port3Active1': [(np.nan,
    #                                                          np.nan)]
    #                                        }
    #                  }

    # error_trial = {'Events timestamps': {'GlobalTimer1_End': [10.0],
    #                                      'Port2In': [2.2133, 3.6032,
    #                                                  4.1014, 4.7648,
    #                                                  5.1329, 5.6429,
    #                                                  6.4632, 6.5842,
    #                                                  6.8691, 7.1565,
    #                                                  7.6357, 7.8717,
    #                                                  8.1396, 8.4102],
    #                                      'Tup': [0.0001],
    #                                      'Port3In': [9.5196],
    #                                      'Port2Out': [2.3768, 3.9778,
    #                                                   4.4069, 5.0538,
    #                                                   5.3777, 5.8241,
    #                                                   6.472, 6.7757,
    #                                                   7.0552, 7.543,
    #                                                   7.7867, 8.0342,
    #                                                   8.273, 8.5793]
    #                                      },
    #                'Bpod start timestamp': 0.117,
    #                'States timestamps': {'correct': [(np.nan, np.nan)],
    #                                      'error': [(0.0001, 10.0)],
    #                                      'TimerTrig': [(0, 0.0001)],
    #                                      'Port3Active1': [(np.nan,
    #                                                        np.nan)]
    #                                      }
    #                }

    # import time
    # # f = open(sph.DATA_FILE_PATH, 'a')
    # next_trial_times = []
    # trial_completed_times = []
    # for x in range(500):

    #     t = time.time()
    #     tph.next_trial()
    #     next_trial_times.append(time.time() - t)
    #     print('next_trial took: ', next_trial_times[-1], '(s)')
    #     t = time.time()
    #     data = tph.trial_completed(random.choice([correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              correct_trial, correct_trial,
    #                                              error_trial, error_trial,
    #                                              error_trial, error_trial,
    #                                               ]))
    #     trial_completed_times.append(time.time() - t)
    #     print('trial_completed took: ', trial_completed_times[-1], '(s)')
    #     print('\n\n')

    # print('Average next_trial times:', sum(next_trial_times)/len(next_trial_times))
    # print('Average trial_completed times:', sum(trial_completed_times)/len(trial_completed_times))
    #     # print(tph.trial_num, tph.contrast, tph.trial_correct,
    #     #       tph.is_reprat_trial)

    # #     f.write(data)
    # #     f.write('\n')
    # # f.close()
    # print('\n\n')
    # trial_data = []
    # with open(sph.DATA_FILE_PATH, 'r') as f:
    #     for line in f:
    #         dict_obj = json.loads(line)
    #         trial_data.append(dict_obj)
    # print(dict_obj)
