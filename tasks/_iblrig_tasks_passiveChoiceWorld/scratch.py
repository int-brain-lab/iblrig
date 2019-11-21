#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, November 15th 2019, 12:05:29 pm
import math

import matplotlib.pyplot as plt
import numpy as np

from iblrig.path_helper import get_iblrig_folder


def make_passiveCW_pcs(seed_num, save=False):
    np.random.seed(seed_num)
    IBLRIG_FOLDER = get_iblrig_folder()
    # Generate the position and contrast for the replayed stims
    contrasts = [1.0, 0.25, 0.125, 0.0625]
    zero_contrasts = [0.0]

    positions = [-35, 35]
    pc_repeats = 20
    # zero % contrast is added with half the amount of pc_repeats
    zero_repeats = len(positions) * pc_repeats / 2

    pos = sorted(positions * len(contrasts) * pc_repeats)
    cont = contrasts * pc_repeats * len(positions)

    pos.extend(positions * (zero_repeats / len(positions)))
    cont.extend(zero_contrasts * zero_repeats)
    sphase = [np.random.uniform(0, math.pi) for x in cont]
    gabors = np.array([[int(p), c, s] for p, c, s in zip(pos, cont, sphase)])

    np.random.shuffle(gabors)
    # Make into strings for saving
    if save:
        data = np.array([[str(int(p)), str(c), str(s)] for p, c, s in gabors])
    fpath = IBLRIG_FOLDER / 'visual_stim' / 'passiveChoiceWorld' / 'Extensions' / 'pcs_stims.csv'
    np.savetxt(fpath, data, delimiter=' ', fmt='#s')
    return gabors


def make_passiveCW_session_delays_id(seed_num, save_session=False):
    np.random.seed(seed_num)

    g_len = np.ones((180)) * 0.3
    n_len = np.ones((40)) * 0.5
    t_len = np.ones((40)) * 0.1
    v_len = np.ones((40)) * 0.2

    g_labels = ['G'] * 180
    n_labels = ['N'] * 40
    t_labels = ['T'] * 40
    v_labels = ['V'] * 40

    g_delay_dist = np.random.uniform(0.500, 1.900, len(g_labels))
    n_delay_dist = np.random.uniform(1, 5, len(n_labels))
    t_delay_dist = np.random.uniform(1, 5, len(t_labels))
    v_delay_dist = np.random.uniform(1, 11, len(v_labels))

    # Calculate when they all should happen
    sess_delays_cumsum = np.concatenate([
        np.cumsum(g_delay_dist),
        np.cumsum(n_delay_dist),
        np.cumsum(t_delay_dist),
        np.cumsum(v_delay_dist)
    ])
    sess_labels_out = np.array(g_labels + n_labels + t_labels + v_labels)

    # Sort acording to the when they happen
    srtd_idx = np.argsort(sess_delays_cumsum)
    sess_delays_cumsum = sess_delays_cumsum[srtd_idx]
    sess_labels_out = sess_labels_out[srtd_idx]
    # get the delays between the stims
    sess_delays_out = np.diff(sess_delays_cumsum)
    tot_dur = np.sum(np.sum(g_len) + np.sum(n_len) + np.sum(t_len) +
                     np.sum(v_len) + np.sum(sess_delays_out)) / 60

    print(f'Stim IDs: {sess_labels_out}')
    print(f'Stim delays: {sess_delays_out}')
    print(f'Total duration of stims: {tot_dur} m')


def pre_generate_passiveCW_session_files():
    pass

if __name__ == "__main__":
    make_passiveCW_session_delays_id(43)
    print('.')
