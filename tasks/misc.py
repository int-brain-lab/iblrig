# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, February 8th 2019, 12:51:51 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 8-02-2019 12:51:53.5353
import numpy as np


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


def draw_contrast(contrast_set, prob_type='biased'):
    if prob_type == 'biased':
        # p = [1/(n-1 + 0.5)] * (n - 1)
        n_1 = len(contrast_set) - 1
        z = n_1 + 0.5
        p = [1/z] * (n_1 + 1)
        p[-1] *= 0.5
        return np.random.choice(contrast_set, p=p)
    elif prob_type == 'uniform':
        return np.random.choice(contrast_set)
