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
tones = ['T'] * 60
noises = ['N'] * 60
valves = ['V'] * 60

gabor_delays = np.random.uniform(0.500, 1.900, len(gabors))
tone_delays = np.random.uniform(1, 5, len(tones))
noise_delays = np.random.uniform(1, 5, len(noises))
valve_delays = np.random.uniform(1, 5, len(valves))

# Trial draws
g_delay = np.random.uniform(0.500, 1.900, 2)
t_delay = np.random.uniform(1, 5, 1)
n_delay = np.random.uniform(1, 5, 1)
v_delay = np.random.uniform(1, 5, 1)

g_delay = np.cumsum(g_delay)
trial_delays = np.sort(np.concatenate((g_delay, t_delay, n_delay, v_delay)))

gabor_len = 0.3
valve_len = 0.05
go_tone_len = 0.1
noise_len = 0.5
