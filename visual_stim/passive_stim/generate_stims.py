#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, June 17th 2019, 2:06:00 pm
"""
Six contrasts are presented (100; 50; 25; 12; 6; 4 %). Each grating is
presented (ON) for 2 s,  with a fixed time interval between gratings (OFF) of
1 s during which the gray background is presented. Each grating is presented 20
times, at each left-right location, in a randomised order.
"""
import numpy as np


CONTRASTS = [1.0, 0.5, 0.25, 0.125, 0.0625]
POSITIONS = [-35, 35]
NREPEAT = 20

pos = sorted(POSITIONS * len(CONTRASTS) * NREPEAT)
cont = CONTRASTS * NREPEAT * 2

data = np.array([[int(p), c] for p, c in zip(pos, cont)])

np.random.shuffle(data)
data = np.array([[str(int(p)), str(c)] for p, c in data])
np.savetxt('stims.csv', data, delimiter=' ', fmt='%s')

