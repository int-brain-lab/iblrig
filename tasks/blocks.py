# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, February 8th 2019, 11:39:30 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 8-02-2019 11:39:33.3333
import misc


def get_block_len(factor, min_, max_):
    return int(misc.texp(factor=factor, min_=min_, max_=max_))


def update_block_params(tph):
    tph.block_trial_num += 1
    if tph.block_trial_num == tph.block_len:
        tph.block_num += 1
        tph.block_trial_num = 1
        tph.block_len = get_block_len(
            factor=tph.block_len_factor, min_=tph.block_len_min,
            max_=tph.block_len_max)

    return tph


def update_probability_left(block_trial_num, stim_probability_left):
    if block_trial_num != 1:
        return stim_probability_left
    elif block_trial_num == 1 and stim_probability_left == 0.2:
        return 0.8
    elif block_trial_num == 1 and stim_probability_left == 0.8:
        return 0.2
