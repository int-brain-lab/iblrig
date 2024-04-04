"""
Creates sessions, pre-generates stim and ephys sessions
"""

import math

import numpy as np

from iblrig import misc


def draw_position(position_set, stim_probability_left) -> int:
    return int(np.random.choice(position_set, p=[stim_probability_left, 1 - stim_probability_left]))


def draw_block_len(factor, min_=20, max_=100):
    return int(misc.truncated_exponential(scale=factor, min_value=min_, max_value=max_))


# EPHYS CHOICE WORLD
def make_ephyscw_pc(prob_type='biased'):
    """make_ephysCW_pc Makes positions, contrasts and block lengths for ephysCW
        Generates ~2000 trias
    :prob_type: (str) 'biased': 0 contrast half has likely to be drawn, 'uniform': 0 contrast as
    likely as other contrasts
    :return: pc
    :rtype: [type]
    """
    contrasts = [1.0, 0.25, 0.125, 0.0625, 0.0]
    len_block = [90]
    pos = [-35] * int(len_block[0] / 2) + [35] * int(len_block[0] / 2)
    cont = np.sort(contrasts * 10)[::-1][:-5].tolist()
    prob = [0.5] * len_block[0]
    pc = np.array([pos, cont + cont, prob]).T
    np.random.shuffle(pc)  # only shuffles on the first dimension

    prob_left = 0.8 if draw_position([-35, 35], 0.5) < 0 else 0.2
    while len(pc) < 2001:
        len_block.append(draw_block_len(60, min_=20, max_=100))
        for _x in range(len_block[-1]):
            p = draw_position([-35, 35], prob_left)
            c = misc.draw_contrast(contrasts, probability_type=prob_type)
            pc = np.append(pc, np.array([[p, c, prob_left]]), axis=0)
            # do this in PC space
        prob_left = np.round(np.abs(1 - prob_left), 1)

    return pc, len_block
