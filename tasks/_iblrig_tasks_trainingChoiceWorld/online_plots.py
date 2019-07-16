#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-20 14:46:10
# matplotlib.use('Qt5Agg')
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def make_fig(sph):
    plt.ion()
    f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
    ax_bars = plt.subplot2grid((2, 2), (0, 0), rowspan=1, colspan=1)
    ax_psych = plt.subplot2grid((2, 2), (0, 1), rowspan=1, colspan=1)
    ax_chron = plt.subplot2grid((2, 2), (1, 0), rowspan=1, colspan=1)
    ax_vars = plt.subplot2grid((2, 2), (1, 1), rowspan=1, colspan=1)
    ax_vars2 = ax_vars.twinx()
    f.canvas.draw_idle()
    plt.show()

    f.suptitle(
        f'{sph.SUBJECT_NAME} - {sph.SUBJECT_WEIGHT}gr - {sph.SESSION_DATETIME}')  # noqa

    axes = (ax_bars, ax_psych, ax_chron, ax_vars, ax_vars2)
    # plt.pause(0.001)
    return (f, axes)


def update_fig(f, axes, tph):
    ax_bars, ax_psych, ax_chron, ax_vars, ax_vars2 = axes

    bar_data = get_barplot_data(tph)
    psych_data = get_psych_data(tph)
    chron_data = get_chron_data(tph)
    vars_data = get_vars_data(tph)

    plot_bars(bar_data, ax=ax_bars)
    plot_psych(psych_data, ax=ax_psych)
    plot_chron(chron_data, ax=ax_chron)
    plot_vars(vars_data, ax=ax_vars, ax2=ax_vars2)
    plt.pause(0.001)

    fname = Path(tph.data_file_path).parent / 'online_plot.png'
    f.savefig(fname)


def get_barplot_data(tph):
    out = {}
    out['trial_num'] = tph.trial_num
    out['ntrials_repeated'] = tph.rc.ntrials
    out['ntrials_adaptive'] = tph.ac.ntrials
    out['ntrials_correct'] = tph.ntrials_correct
    out['ntrials_err'] = out['trial_num'] - out['ntrials_correct']
    out['water_delivered'] = np.round(tph.water_delivered, 3)
    out['time_from_start'] = tph.elapsed_time
    return out


def get_psych_data(tph):
    sig_contrasts_all = np.array(tph.contrast_set)
    sig_contrasts_all = np.append(
        sig_contrasts_all, [-x for x in sig_contrasts_all if x != 0])
    sig_contrasts_all = np.sort(sig_contrasts_all)

    sig_contrast_buffer = np.array(tph.signed_contrast_buffer)
    response_side_buffer = np.array(tph.response_side_buffer)

    ntrials_ccw = np.array([
        sum(response_side_buffer[sig_contrast_buffer == x] < 0)
        for x in sig_contrasts_all])
    ntrials = np.array(
        [sum(sig_contrast_buffer == x) for x in sig_contrasts_all])

    prop_resp_ccw = [x / y if y != 0 else 0 for x, y in zip(ntrials_ccw,
                                                            ntrials)]
    return sig_contrasts_all, prop_resp_ccw


def get_chron_data(tph):
    sig_contrasts_all = tph.contrast_set.copy()
    sig_contrasts_all.extend([-x for x in sig_contrasts_all])
    sig_contrasts_all = np.sort(sig_contrasts_all)

    signed_contrast_buffer = np.array(tph.signed_contrast_buffer)
    resopnse_time_buffer = np.array(tph.response_time_buffer)
    rts = [np.median(resopnse_time_buffer[signed_contrast_buffer == x])
           for x in sig_contrasts_all]
    rts = [x if not np.isnan(x) else 0 for x in rts]

    return sig_contrasts_all, rts


def get_vars_data(tph):
    out = {}
    out['median_rt'] = np.median(tph.response_time_buffer) * 1000
    out['prop_correct'] = tph.ntrials_correct / tph.trial_num
    out['Temperature_C'] = tph.as_data['Temperature_C']
    out['AirPressure_mb'] = tph.as_data['AirPressure_mb']
    out['RelativeHumidity'] = tph.as_data['RelativeHumidity']
    return out


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
    y = [0 if np.isnan(i) else i for i in y]

    ax.plot(x, y, c='k', label='CCW responses', marker='o', ls='-')

    ax.axhline(0.5, color='gray', ls='--', alpha=0.5)
    ax.axvline(0.0, color='gray', ls='--', alpha=0.5)
    ax.set_ylim([-0.1, 1.1])
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
    y = [0 if np.isnan(i) else i for i in y]

    ax.plot(x, y, c='k', label='Median time to respond', marker='o', ls='-')

    ax.axhline(0.5, color='gray', ls='--', alpha=0.5)
    ax.axvline(0.0, color='gray', ls='--', alpha=0.5)
    ax.legend(loc='best')
    ax.grid()
    ax.figure.canvas.draw_idle()
    return


def plot_vars(vars_data, ax=None, ax2=None):
    if ax is None:
        # f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
        ax = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)
        ax2 = ax.twinx()
    if ax2 is None:
        ax2 = ax.twinx()

    ax.cla()
    ax2.cla()

    # ax.figure.tight_layout()  # or right y-label is slightly clipped
    width = 0.75

    x = [0, 1, 2, 3, 4]
    median_rt = vars_data['median_rt'] / 10
    prop_correct = vars_data['prop_correct']
    temp = vars_data['Temperature_C']
    rel_hum = vars_data['RelativeHumidity'] / 100

    ax.bar(x[0], median_rt, width, color="cyan",
           label='Median RT (10^1ms)')
    ax.bar(x[1], temp, width, color="magenta",
           label='Temperature (ºC)')

    ax2.bar(x[3], rel_hum, width, color="yellow",
            label='Relative humidity')
    ax2.bar(x[4], prop_correct, width, color="black",
            label='Proportion correct')
    ax2.set_ylim([0, 1.1])
    ax.legend(loc='lower left')
    ax2.legend(loc='lower right')
    ax.figure.canvas.draw_idle()
    ax2.figure.canvas.draw_idle()


if __name__ == '__main__':
    pass
