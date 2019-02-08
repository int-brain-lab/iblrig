# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, February 8th 2019, 12:51:51 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 8-02-2019 12:51:53.5353
import numpy as np
import datetime
from pathlib import Path


def get_port_events(events: dict, name: str = '') -> list:
    out: list = []
    for k in events:
        if name in k:
            out.extend(events[k])
    out = sorted(out)

    return out


def update_buffer(buffer: list, val) -> list:
        buffer = np.roll(buffer, -1, axis=0)
        buffer[-1] = val
        return buffer.tolist()


def texp(factor: float = 0.35, min_: float = 0.2, max_: float = 0.5) -> float:
        """Truncated exponential
        mean = 0.35
        min = 0.2
        max = 0.5
        """
        x = np.random.exponential(factor)
        if min_ <= x <= max_:
            return x
        else:
            return texp(factor=factor, min_=min_, max_=max_)


def draw_contrast(contrast_set, prob_type='biased') -> float:
    if prob_type == 'biased':
        # p = [1/(n-1 + 0.5)] * (n - 1)
        n_1 = len(contrast_set) - 1
        z = n_1 + 0.5
        p = [1/z] * (n_1 + 1)
        p[-1] *= 0.5
        return np.random.choice(contrast_set, p=p)
    elif prob_type == 'uniform':
        return np.random.choice(contrast_set)


def check_stop_criterions(init_datetime, rt_buffer, trial_num) -> int:
        # STOPPING CRITERIONS
        # < than 400 trials in 45 minutes
        time_up = init_datetime + datetime.timedelta(minutes=45)
        if time_up <= datetime.datetime.now() and trial_num <= 400:
            return 1

        # Median response time of latest N = 20 trials > than 5 times
        # the median response time and more than 400 trials performed
        N, T = 20, 400
        if len(rt_buffer) >= N and trial_num > T:
            latest_median = np.median(rt_buffer[-N:])
            all_median = np.median(rt_buffer)

            if latest_median > all_median * 5:
                return 2

        return False


def get_trial_rt(behavior_data) -> float:
    return (behavior_data['States timestamps']['closed_loop'][0][1] -
            behavior_data['States timestamps']['stim_on'][0][0])


def create_flags(data_file_path, poop_count) -> None:
    flag = Path(data_file_path).parent.parent / 'transfer_me.flag'
    open(flag, 'a').close()
    flag2 = Path(data_file_path).parent.parent / 'create_me.flag'
    open(flag2, 'a').close()
    flag3 = Path(data_file_path).parent.parent / 'poop_count.flag'
    if poop_count:
        open(flag3, 'a').close()
