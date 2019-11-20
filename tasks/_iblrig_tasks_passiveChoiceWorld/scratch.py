#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, November 15th 2019, 12:05:29 pm
import matplotlib.pyplot as plt
import numpy as np
from iblrig.path_helper import get_iblrig_folder

np.random.seed(42)

IBLRIG_FOLDER = get_iblrig_folder()
# Generate the position and contrast for the replayed stims
CONTRASTS = [1.0, 0.25, 0.125, 0.0625]
ZERO_CONTRASTS = [0.0]

POSITIONS = [-35, 35]
NREPEAT = 20

pos = sorted(POSITIONS * len(CONTRASTS) * NREPEAT)
cont = CONTRASTS * NREPEAT * 2
pos.extend(POSITIONS * 10)
cont.extend(ZERO_CONTRASTS * 20)
gabors = np.array([[int(p), c] for p, c in zip(pos, cont)])

np.random.shuffle(gabors)
# Make into strings for saving
# data = np.array([[str(int(p)), str(c)] for p, c in data])
# fpath = IBLRIG_FOLDER / 'visual_stim' / 'passive_stim' / 'stims.csv'
# np.savetxt(fpath, data, delimiter=' ', fmt='#s')
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

g_delays = np.cumsum(g_delay_dist) + g_len
n_delays = np.cumsum(n_delay_dist) + n_len
t_delays = np.cumsum(t_delay_dist) + t_len
v_delays = np.cumsum(v_delay_dist) + v_len


sess_delays = np.concatenate([g_delays, n_delays, t_delays, v_delays])
sess_labels = np.array(g_labels + n_labels + t_labels + v_labels)
sess_lens = np.concatenate([g_len, n_len, t_len, v_len])

# Sort acording to the delays
srtd_idx = np.argsort(sess_delays)

sess_delays = sess_delays[srtd_idx]
sess_labels = sess_labels[srtd_idx]
sess_lens = sess_lens[srtd_idx]
# Add previous stim duration to delay
# temp_delays = sess_delays[:-1] + sess_lens[1:]
# sess_delays = np.insert(temp_delays, 0, sess_delays[0])

# Check if the min diff is reasonable
mindiff = np.min(np.diff(sess_delays))
amin = np.argmin(np.diff(sess_delays))

print(sess_labels[amin - 1:amin + 2])
print(sess_delays[amin - 1:amin + 2])
print(mindiff)
