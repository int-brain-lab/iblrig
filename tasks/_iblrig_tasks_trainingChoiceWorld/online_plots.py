# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-20 14:46:10
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-05-30 17:31:48
# matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
import pandas as pd


def make_fig(sph):
    plt.ion()
    f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
    ax_bars = plt.subplot2grid((2, 2), (0, 0), rowspan=1, colspan=1)
    ax_psych = plt.subplot2grid((2, 2), (0, 1), rowspan=1, colspan=1)
    ax_chron = plt.subplot2grid((2, 2), (1, 0), rowspan=1, colspan=1)
    ax_vars = plt.subplot2grid((2, 2), (1, 1), rowspan=1, colspan=1)
    f.canvas.draw_idle()
    plt.show()

    f.suptitle(
        f'{sph.SUBJECT_NAME} - {sph.SUBJECT_WEIGHT}gr - {sph.SESSION_DATETIME}')  # noqa

    axes = (ax_bars, ax_psych, ax_chron, ax_vars)
    # plt.pause(0.001)
    return (f, axes)


def update_fig(f, axes, tph):
    ax_bars, ax_psych, ax_chron, ax_vars = axes

    bar_data = get_barplot_data(tph)
    psych_data = get_psych_data(tph)
    chron_data = get_chron_data(tph)
    vars_data = get_vars_data(tph)

    plot_bars(bar_data, ax=ax_bars)
    plot_psych(psych_data, ax=ax_psych)
    plot_chron(chron_data, ax=ax_chron)
    plot_vars(vars_data, ax=ax_vars)
    plt.pause(0.001)


def get_barplot_data(tph):
    out = {}
    out['trial_num'] = tph.trial_num
    out['ntrials_repeated'] = tph.rc.ntrials
    out['ntrials_adaptive'] = tph.ac.ntrials
    out['ntrials_correct'] = tph.ntrials_correct
    out['ntrials_err'] = out['trial_num'] - out['ntrials_correct']
    out['water_delivered'] = tph.water_delivered
    out['time_from_start'] = tph.elapsed_time
    return out


def get_psych_data(tph):
    sig_contrasts_all = [
        -1., -0.5, -0.25, -0.125, -0.0625, 0., 0.0625, 0.125, 0.25, 0.5, 1.]
    sig_contrasts = np.array(tph.signed_contrast_buffer)
    print(sig_contrasts)
    response_side_buffer = np.array(tph.response_side_buffer)
    print(response_side_buffer)
    ntrials_ccw = [sum(response_side_buffer[sig_contrasts == x] < 0)
                   for x in sig_contrasts_all]
    ntrials = np.array(
        [sum(sig_contrasts == x) for x in sig_contrasts_all])
    prop_resp_ccw = ntrials_ccw / ntrials
    return sig_contrasts_all, prop_resp_ccw


def get_chron_data(tph):
    sig_contrasts_all = [
        - 1., - 0.5, -0.25, -0.125, -0.0625, 0., 0.0625, 0.125, 0.25, 0.5, 1.]
    sig_contrasts = np.array(tph.signed_contrast_buffer)
    resopnse_time_buffer = np.array(tph.response_time_buffer)
    print(resopnse_time_buffer)
    rts = [np.median(resopnse_time_buffer[sig_contrasts == x])
           for x in sig_contrasts_all]
    return sig_contrasts_all, rts


def get_vars_data(tph):
    median_rt = np.median(tph.response_time_buffer)
    prop_correct = tph.ntrials_correct / tph.non_rc_ntrials
    return median_rt, prop_correct


# plotters

def plot_bars(bar_data, ax=None):
    if ax is None:
        # f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
        ax = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)
    ax.cla()

    def make_bar_texts(ax, ypos, vars):
        left = 0
        for var in vars:
            ax.text(left + (var * .15), ypos, str(var), color='black',
                    fontweight='bold', size='x-large')
            left += var
        else:
            ax.text(left + (var * .15), ypos, str(left), color='black',
                    fontweight='bold', size='x-large', alpha=0.5)
    width = 0.75
    xlabels = ['Water\nDelivered\n(µl)', 'Performance',
               'Trial\nTypes', 'Session\nDuration']
    y = [bar_data['trial_num'], bar_data['ntrials_correct'],
         bar_data['water_delivered'], 0]
    x = range(len(xlabels))  # the x locations for the groups

    ax.barh(3, 0, width, color="black")
    # ax.barh(0, bar_data['trial_num'], width, color="gray")

    ax.text(max(y) / 10, 3, str(bar_data['time_from_start']),
            color='black', fontweight='bold', size='x-large')

    ax.barh(2, bar_data['ntrials_repeated'], width, color="pink",
            label='Repeated')
    ax.barh(2, bar_data['ntrials_adaptive'], width,
            left=bar_data['ntrials_repeated'], color="orange",
            label='Adaptive')
    make_bar_texts(ax, 2, [bar_data['ntrials_repeated'],
                   bar_data['ntrials_adaptive']])

    ax.barh(1, bar_data['ntrials_correct'], width, color="green",
            label='Correct')
    ax.barh(1, bar_data['ntrials_err'], width,
            left=bar_data['ntrials_correct'], color="red", label='Error')
    make_bar_texts(ax, 1, [bar_data['ntrials_correct'],
                   bar_data['ntrials_err']])

    ax.barh(0, bar_data['water_delivered'], width, color="blue")
    ax.text(bar_data['water_delivered'] + 1, 0,
            str(bar_data['water_delivered']), color='blue', fontweight='bold',
            size='x-large')

    ax.set_yticks([i for i in x])
    ax.set_yticklabels(xlabels, minor=False)
    ax.set_xlim([0, max(y) + (max(y) * 0.2)])
    ax.legend()
    ax.figure.canvas.draw_idle()


def plot_psych(psych_data, ax=None):

    if ax is None:
        # f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
        ax = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)
    ax.cla()

    x = psych_data[0]
    y = psych_data[1]

    ax.plot(x, y, c='k', label='CCW responses', ls='-.')

    ax.axhline(0.5, color='gray', ls='--', alpha=0.5)
    ax.axvline(0.5, color='gray', ls='--', alpha=0.5)
    ax.set_ylim([0, 1])
    ax.legend(loc='best')
    ax.grid()
    ax.figure.canvas.draw_idle()
    return


def plot_chron(chron_data, ax=None):
    if ax is None:
        # f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
        ax = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)
    ax.cla()

    x = chron_data[0]
    y = chron_data[1]

    ax.plot(x, y, c='k', label='Time to respond', ls='-.')

    ax.axhline(0.5, color='gray', ls='--', alpha=0.5)
    ax.axvline(0.5, color='gray', ls='--', alpha=0.5)
    ax.legend(loc='best')
    ax.grid()
    ax.figure.canvas.draw_idle()
    return


def plot_vars(vars_data, ax=None):
    if ax is None:
        # f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
        ax = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)
    ax.cla()
    width = 0.75

    x = [0, 1]
    median_rt = vars_data[0]
    prop_correct = vars_data[1]

    ax.bar(x[0], median_rt, width, color="cyan",
            label='Median RT')
    ax.bar(x[1], prop_correct, width, color="green",
            label='Proportion correct')
    ax.legend(loc='best')
    ax.figure.canvas.draw_idle()


if __name__ == '__main__':
    pass
