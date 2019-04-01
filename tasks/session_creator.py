# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, March 28th 2019, 7:19:15 pm
import random
import math

import numpy as np

import blocks
import misc


def make_pc():
    contrasts = [1., 0.25, 0.125, 0.0625, 0.0]
    len_block = [90]
    pos = [-35] * int(len_block[0] / 2) + [35] * int(len_block[0] / 2)
    cont = np.sort(contrasts * 10)[::-1][:-5].tolist()
    pc = np.array([pos, cont+cont]).T
    np.random.shuffle(pc)  # only shuffles on the first dimension

    prob_left = 0.8 if blocks.draw_position([-35, 35], 0.5) < 0 else 0.2
    while len(pc) < 2001:
        len_block.append(blocks.get_block_len(60, min_=20, max_=100))
        for x in range(len_block[-1]):
            p = blocks.draw_position([-35, 35], prob_left)
            c = misc.draw_contrast(contrasts)
            pc = np.append(pc, np.array([[p, c]]), axis=0)
            # do this in PC space
        prob_left = np.round(np.abs(1 - prob_left), 1)

    return pc, len_block


def make_pcqs(pc):
    qperiod_base = 0.2  # + x, where x~exp(0.35), t ∈ 0.2 <= R <= 0.5
    sphase = []
    qperiod = []
    for i in pc:
        sphase.append(random.uniform(0, math.pi))
        qperiod.append(qperiod_base + misc.texp(factor=0.35, min_=0.2, max_=0.5))
    qs = np.array([qperiod, sphase]).T
    pcqs = np.append(pc, qs, axis=1)
    return pcqs


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from ibllib.dsp.smooth import smooth
    pc, len_block = make_pc()
    pcqs = make_pcqs(pc)
    pos = pcqs[:, 0]
    plt.plot(pcqs[:, 0], '.', label='Position')
    plt.plot(smooth(pcqs[:, 0], window_len=20, window='blackman'), alpha=0.5, color='k')
    plt.plot(pcqs[:, 1], '.', label='Contrast')
    plt.plot(pcqs[:, 2], '.', label='Quiescent period')
    plt.plot(pcqs[:, 3], '.', label='Stimulus phase')
    plt.legend(loc='best')
    [plt.axvline(x) for x in np.cumsum(len_block)]
    plt.show()

    print('.')
