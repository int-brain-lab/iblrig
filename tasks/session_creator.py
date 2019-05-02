#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, March 28th 2019, 7:19:15 pm
import random
import math

import numpy as np
import matplotlib.pyplot as plt

import blocks
import misc
from ibllib.dsp.smooth import smooth


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
        qperiod.append(
            qperiod_base + misc.texp(factor=0.35, min_=0.2, max_=0.5))
    qs = np.array([qperiod, sphase]).T
    pcqs = np.append(pc, qs, axis=1)
    return pcqs


def generate_sessions(nsessions, path=None):
    for i in range(nsessions):
        pc, len_block = make_pc()
        pcqs = make_pcqs(pc)
        if path is None:
            path = 'tasks/_iblrig_tasks_ephysChoiceWorld/sessions/'
        np.save(path + f'pcqs_session_{i}.npy', pcqs)
        np.save(path + f'pcqs_session_{i}_len_blocks.npy', len_block)


def plot_pcqs(session_num):
    num = session_num
    task = 'tasks/_iblrig_tasks_ephysChoiceWorld/'
    pcqs = np.load(task + f'sessions/pcqs_session_{num}.npy')
    len_block = np.load(task + f'sessions/pcqs_session_{num}_len_blocks.npy')

    with plt.xkcd(scale=1, length=100, randomness=2):
        f = plt.figure(figsize=(16, 12), dpi=80)
        f.suptitle(f'Session number: {num}')
        ax_position = plt.subplot2grid(
            [2, 2], [0, 0], rowspan=1, colspan=1, fig=f)
        ax_contrast = plt.subplot2grid(
            [2, 2], [0, 1], rowspan=1, colspan=1, fig=f, sharex=ax_position)
        ax_qperiod = plt.subplot2grid(
            [2, 2], [1, 0], rowspan=1, colspan=1, fig=f, sharex=ax_position)
        ax_sphase = plt.subplot2grid(
            [2, 2], [1, 1], rowspan=1, colspan=1, fig=f, sharex=ax_position)

    ax_position.plot(pcqs[:, 0], '.', label='Position', color='b')
    ax_position.plot(
        smooth(pcqs[:, 0], window_len=20, window='blackman'),
        alpha=0.5, color='k')

    ax_contrast.plot(pcqs[:, 1] * 100, '.', label='Contrasts')

    ax_qperiod.plot(pcqs[:, 2], '.', label='Quiescent period')

    ax_sphase.plot(pcqs[:, 3], '.', label='Stimulus phase')

    [ax.set_ylabel(l) for ax, l in zip(f.axes, ['Position (º)',
                                                'Contrasts (%)',
                                                'Quiescent period (s)',
                                                'Stimulus phase (rad)'])]
    [ax.axvline(x, alpha=0.5) for x in np.cumsum(len_block) for ax in f.axes]
    f.show()
    return pcqs, len_block


if __name__ == "__main__":
    import seaborn as sns
    plt.ion()
    # pcqs3, len_block3 = plot_pcqs(3)
    pcqs9, len_block9 = plot_pcqs(9)
    # sns.distplot(pcqs3[:, 2], vertical=True)
    # sns.jointplot(x=range(len(pcqs9)), y=pcqs9[:, 1])
    qp = sns.jointplot(x=range(len(pcqs9)),
                       y=pcqs9[:, 2], kind='kde', figsize=(16, 12), dpi=80)
    qp.set_axis_labels(xlabel='Trials', ylabel='Quiescent period (s)')

    print('.')
