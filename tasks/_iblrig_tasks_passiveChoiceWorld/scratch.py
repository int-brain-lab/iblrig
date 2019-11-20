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


def guniform(min_, max_, len_):
    for x in np.random.uniform(min_, max_, len_):
        yield x


delay_dists = {
    'G': guniform(0.500, 1.900, len(g_labels)),
    'N': guniform(1, 5, len(n_labels)),
    'T': guniform(1, 5, len(t_labels)),
    'V': guniform(1, 11, len(v_labels))
}
stim_delays = np.random.uniform(0.25, 0.85, 300)
stim_labels = np.array(g_labels + n_labels + t_labels + v_labels)
np.random.shuffle(stim_labels)
for i, (d, l) in enumerate(zip(stim_delays, stim_labels)):
    if i == 0:
        pass
    else:
        if stim_labels[i - 1] == stim_labels[i]:
            stim_delays[i] = next(delay_dists[l])

np.cumsum(stim_delays)[-1] / 60
