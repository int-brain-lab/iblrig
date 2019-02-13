# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, February 8th 2019, 11:39:30 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 8-02-2019 11:39:33.3333
import misc
import numpy as np


def get_block_len(factor, min_, max_):
    return int(misc.texp(factor=factor, min_=min_, max_=max_))


def update_block_params(tph):
    tph.block_trial_num += 1
    if tph.block_trial_num > tph.block_len:
        tph.block_num += 1
        tph.block_trial_num = 1
        tph.block_len = get_block_len(
            factor=tph.block_len_factor, min_=tph.block_len_min,
            max_=tph.block_len_max)

    return tph


def update_probability_left(tph):
    if tph.block_trial_num != 1:
        return tph.stim_probability_left

    if tph.block_num == 1 and tph.block_init_5050:
        return 0.5
    elif tph.block_num == 1 and not tph.block_init_5050:
        return np.random.choice(tph.block_probability_set)
    elif tph.block_num == 2 and tph.block_init_5050:
        return np.random.choice(tph.block_probability_set)
    elif tph.stim_probability_left == 0.2:
        return 0.8
    elif tph.stim_probability_left == 0.8:
        return 0.2


def draw_position(position_set, stim_probability_left):
    return int(np.random.choice(
        position_set, p=[stim_probability_left, 1 - stim_probability_left]))


def init_block_len(tph):
    if tph.block_init_5050:
        return 90
    else:
        return get_block_len(
            factor=tph.block_len_factor, min_=tph.block_len_min,
            max_=tph.block_len_max)


def init_probability_left(tph):
    if tph.block_init_5050:
        return 0.5
    else:
        return np.random.choice(tph.block_probability_set)
