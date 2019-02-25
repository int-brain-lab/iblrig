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


def p_hat_err(X, n, error=False):
    """ Probabilities and Errors calculated using
    https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
    #Agresti%E2%80%93Coull_interval """
    alpha = 0.05
    z = 1 - (alpha / 2)
    n_hat = n + z**2
    p_hat = (1 / n_hat) * (X + ((z**2) / 2))
    err = z * np.sqrt((p_hat / n_hat) * (1 - p_hat))
    return (p_hat, err) if error else p_hat


def get_barplot_data(tph):
    trial_data = tph.__dict__
    out = {}
    out['trial_num'] = trial_data['trial_num']
    out['ntrials_repeated'] = trial_data['rc']['ntrials']
    out['ntrials_adaptive'] = trial_data['ac']['ntrials']
    out['ntrials_correct'] = trial_data['ntrials_correct']
    out['ntrials_err'] = out['trial_num'] - out['ntrials_correct']
    out['water_delivered'] = trial_data['water_delivered']
    out['time_from_start'] = trial_data['elapsed_time']
    return out


def get_psych_data(tph):
    trial_data = tph.__dict__
    sig_contrasts_all = [
        -1., -0.5, -0.25, -0.125, -0.0625, 0., 0.0625, 0.125, 0.25, 0.5, 1.]
    sig_contrasts = np.array(trial_data['signed_contrast_buffer'])
    response_side_buffer = np.array(trial_data['response_side_buffer'])
    n_responses_right = [sum(response_side_buffer[sig_contrasts == x] > 0)
                         for x in sig_contrasts_all]
    p_hat_right = [
        p_hat_err(x, trial_data['non_rc_trials']) for x in n_responses_right]
    return sig_contrasts_all, p_hat_right


def get_chron_data(tph):
    trial_data = tph.__dict__
    sig_contrasts_all = [
        - 1., - 0.5, -0.25, -0.125, -0.0625, 0., 0.0625, 0.125, 0.25, 0.5, 1.]
    sig_contrasts = np.array(trial_data['signed_contrast_buffer'])
    resopnse_time_buffer = np.array(trial_data['resopnse_time_buffer'])
    rts = [np.median(resopnse_time_buffer[sig_contrasts == x])
           for x in sig_contrasts_all]
    return sig_contrasts_all, rts


def get_vars_data(tph):
    trial_data = tph.__dict__
    median_rt = np.median(trial_data['response_time_buffer'])
    prop_correct = trial_data['ntrials_correcr'] / trial_data['non_rc_trials']
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

    ax.plot(x, y, c='k')

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

    ax.plot(x, y, c='k')

    ax.axhline(0.5, color='gray', ls='--', alpha=0.5)
    ax.axvline(0.5, color='gray', ls='--', alpha=0.5)
    ax.set_ylim([0, 1])
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

    ax.barv(x[0], median_rt, width, color="cyan",
            label='Median RT')
    ax.barv(x[1], prop_correct, width, color="green",
            label='Median RT')
    ax.figure.canvas.draw_idle()


if __name__ == '__main__':
    data_file = '/home/nico/Projects/IBL/IBL-github/iblrig/Subjects/\
test_mouse/2018-05-08/13/pycw_basic.data.json'

    def load_raw_data(data_file):
        data = []
        with open(data_file, 'r') as f:
            for line in f:
                data.append(json.loads(line))
        return data

    def session_df_from_path(data_file, repeat_trials=False):
        data = load_raw_data(data_file)

        trial_type = pd.Series([x['trial']['type'] for x in data],
                               name='trial_type')
        contrast = pd.Series([x['contrast'] for x in data], name='contrast')
        position = pd.Series([x['position'] for x in data], name='position')
        correct = pd.Series([x['trial_correct'] for x in data], name='correct')
        response_right = pd.Series(((position == 90) & ~correct) |
                                   ((position == -90) & correct),
                                   name='response_right')
        response_left = pd.Series(((position == 90) & correct) |
                                  ((position == -90) & ~correct),
                                  name='response_left')
        signed_contrast = pd.Series(contrast * np.sign(position),
                                    name='signed_contrast')

        trials = [trial_type, contrast, position, correct, response_right,
                  response_left, signed_contrast]

        df = pd.concat(trials, axis=1)

        no_repeat = df[df.trial_type != 'RepeatContrast']
        return df if repeat_trials else no_repeat

    def psyfun_df_from_path(data_file, repeat_trials=False):
        df = session_df_from_path(data_file, repeat_trials=repeat_trials)

        psyfunR = df.groupby('signed_contrast').response_right.mean()
        psyfunR.name = 'mean_response_right'
        psyfunL = df.groupby('signed_contrast').response_left.mean()
        psyfunL.name = 'mean_response_left'
        psyfunsem = df.groupby('signed_contrast').response_right.sem()
        psyfunsem.name = 'sem'
        out_df = pd.concat([psyfunR, psyfunL, psyfunsem], axis=1)

        return out_df

    data = load_raw_data(data_file)
    trial_data = data[-1]
    psyfun_df = make_psyfun_df()
    f, ax_bars, ax_psyc = make_fig()

    i = -1
    trial_data = data[i]

    plot_bars(trial_data, ax=ax_bars)
    for trial_data in data:
        interval = update_psyfun_df(trial_data, psyfun_df)

    plot_psyfun(trial_data, psyfun_df, ax=ax_psyc)
