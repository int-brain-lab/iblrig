#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, November 15th 2019, 12:05:29 pm
import matplotlib.pyplot as plt
import numpy as np

np.random.seed(42)

# Generate the position and contrast for the replayed stims
CONTRASTS = [1.0, 0.25, 0.125, 0.0625]
POSITIONS = [-35, 35]
NREPEAT = 20

pos = sorted(POSITIONS * len(CONTRASTS) * NREPEAT)
cont = CONTRASTS * NREPEAT * 2

data = np.array([[int(p), c] for p, c in zip(pos, cont)])

np.random.shuffle(data)
data = np.array([[str(int(p)), str(c)] for p, c in data])



gabor_contrasts = [0.0625, 0.125, 0.25, 1] * 20 * 2
gabor_contrasts.extend([0] * 20)
np.random.shuffle(gabor_contrasts)
gabor_delays = np.random.uniform(0.500, 1.900, 180)



gabor_len = 0.3
valve_len = 0.05
go_tone_len = 0.1
noise_len = 0.5

