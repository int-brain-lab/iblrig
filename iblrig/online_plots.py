import datetime
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pandas.api.types import CategoricalDtype

import one.alf.io
from iblrig.choiceworld import get_subject_training_info
from iblrig.misc import online_std
from iblrig.raw_data_loaders import load_task_jsonable
from iblutil.util import Bunch

NTRIALS_INIT = 2000
NTRIALS_PLOT = 20  # do not edit - this is used also to enforce the completion criteria
CONTRAST_SET = np.array([0, 1 / 16, 1 / 8, 1 / 4, 1 / 2, 1])
PROBABILITY_SET = np.array([0.2, 0.5, 0.8])
# if the mouse does less than 400 trials in the first 45mins it's disengaged
ENGAGED_CRITIERION = {'secs': 45 * 60, 'trial_count': 400}
sns.set_style('darkgrid')


class DataModel:
    """
    The data model is a pure numpy / pandas container for the choice world task.
    It contains:
    - a psychometrics dataframe that contains the count / choice and response time
    per signed contrast and block contingency
    - a last trials dataframe that contains 20 trials worth of data for the timeline view
    - various counters such as ntrials and water delivered
    """

    task_settings = None

    def __init__(self, task_file):
        """
        Can be instantiated empty or from an existing jsonable file from any rig version
        :param task_file:
        """
        self.session_path = one.alf.files.get_session_path(task_file) or ''
        self.last_trials = pd.DataFrame(
            columns=['correct', 'signed_contrast', 'stim_on', 'play_tone', 'reward_time', 'error_time', 'response_time'],
            index=np.arange(NTRIALS_PLOT),
        )

        if task_file is None or not Path(task_file).exists():
            self.psychometrics = pd.DataFrame(
                columns=['count', 'response_time', 'choice', 'response_time_std', 'choice_std'],
                index=pd.MultiIndex.from_product([PROBABILITY_SET, np.r_[-np.flipud(CONTRAST_SET[1:]), CONTRAST_SET]]),
            )
            self.psychometrics['count'] = 0
            self.trials_table = pd.DataFrame(columns=['response_time'], index=np.arange(NTRIALS_INIT))
            self.ntrials = 0
            self.ntrials_correct = 0
            self.ntrials_nan = np.nan
            self.percent_correct = np.nan
            self.percent_error = np.nan
            self.water_delivered = 0
            self.time_elapsed = 0
            self.ntrials_engaged = 0  # those are the trials happening within the first 400s
        else:
            self.get_task_settings(Path(task_file).parent)
            trials_table, bpod_data = load_task_jsonable(task_file)
            # here we take the end time of the first trial as reference to avoid factoring in the delay
            self.time_elapsed = bpod_data[-1]['Trial end timestamp'] - bpod_data[0]['Trial end timestamp']
            trials_table['signed_contrast'] = np.sign(trials_table['position']) * trials_table['contrast']
            trials_table['choice'] = trials_table['position'] > 0
            trials_table.loc[~trials_table.trial_correct, 'choice'] = ~trials_table['choice'][~trials_table.trial_correct]
            trials_table['contrast'] = trials_table['contrast'].astype(
                CategoricalDtype(categories=np.unique(np.r_[-CONTRAST_SET, CONTRAST_SET]), ordered=True)
            )
            trials_table['stim_probability_left'] = trials_table['stim_probability_left'].astype(
                CategoricalDtype(categories=PROBABILITY_SET, ordered=True)
            )
            self.psychometrics = trials_table.groupby(['stim_probability_left', 'signed_contrast']).agg(
                count=pd.NamedAgg(column='signed_contrast', aggfunc='count'),
                response_time=pd.NamedAgg(column='response_time', aggfunc=np.nanmean),
                choice=pd.NamedAgg(column='choice', aggfunc='mean'),
                response_time_std=pd.NamedAgg(column='response_time', aggfunc=np.nanstd),
                choice_std=pd.NamedAgg(column='choice', aggfunc=np.nanmean),
            )
            self.ntrials = trials_table.shape[0]
            self.ntrials_correct = np.sum(trials_table.trial_correct)
            self.ntrials_nan = self.ntrials if self.ntrials > 0 else np.nan
            self.percent_correct = self.ntrials_correct / self.ntrials_nan * 100
            # agg.water_delivered = trials_table.water_delivered.iloc[-1]
            self.water_delivered = trials_table.reward_amount.sum()
            # init the last trials table
            it = self.last_trials.index[-np.minimum(self.ntrials, NTRIALS_PLOT) :]
            self.last_trials.loc[it, 'correct'] = trials_table.trial_correct.iloc[-NTRIALS_PLOT:].values
            self.last_trials.loc[it, 'signed_contrast'] = trials_table.signed_contrast.iloc[-NTRIALS_PLOT:].values
            self.last_trials.loc[it, 'response_time'] = trials_table.response_time.iloc[-NTRIALS_PLOT:].values
            self.last_trials.loc[it, 'stim_on'] = np.array(
                [bpod_data[i]['States timestamps']['stim_on'][0][0] for i in np.arange(-it.size, 0)]
            )
            self.last_trials.loc[it, 'play_tone'] = np.array(
                [bpod_data[i]['States timestamps']['play_tone'][0][0] for i in np.arange(-it.size, 0)]
            )
            self.last_trials.loc[it, 'reward_time'] = np.array(
                [bpod_data[i]['States timestamps']['reward'][0][0] for i in np.arange(-it.size, 0)]
            )
            self.last_trials.loc[it, 'error_time'] = np.array(
                [bpod_data[i]['States timestamps']['error'][0][0] for i in np.arange(-it.size, 0)]
            )
            # we keep only a single column as buffer
            self.trials_table = trials_table[['response_time']]
        # for the trials plots this is the background image showing green if correct, red if incorrect
        self.rgb_background = np.ones((NTRIALS_PLOT, 1, 3), dtype=np.uint8) * 229
        self.rgb_background[self.last_trials.correct == False, 0, 0] = 255  # noqa
        self.rgb_background[self.last_trials.correct == True, 0, 1] = 255  # noqa
        # keep the last contrasts as a 20 by 2 array
        ileft = np.where(self.last_trials.signed_contrast < 0)[0]  # negative position is left
        iright = np.where(self.last_trials.signed_contrast > 0)[0]
        self.last_contrasts = np.zeros((NTRIALS_PLOT, 2))
        self.last_contrasts[ileft, 0] = np.abs(self.last_trials.signed_contrast[ileft])
        self.last_contrasts[iright, 1] = np.abs(self.last_trials.signed_contrast[iright])

    def get_task_settings(self, session_directory: str | Path) -> None:
        task_settings_file = Path(session_directory).joinpath('_iblrig_taskSettings.raw.json')
        if not task_settings_file.exists():
            return
        with open(task_settings_file) as fid:
            self.task_settings = json.load(fid)

    def update_trial(self, trial_data, bpod_data) -> None:
        # update counters
        self.time_elapsed = bpod_data['Trial end timestamp'] - bpod_data['Bpod start timestamp']
        if self.time_elapsed <= (ENGAGED_CRITIERION['secs']):
            self.ntrials_engaged += 1
        self.ntrials += 1
        self.water_delivered += trial_data.reward_amount
        self.ntrials_correct += trial_data.trial_correct
        signed_contrast = np.sign(trial_data['position']) * trial_data['contrast']
        choice = trial_data.position > 0 if trial_data.trial_correct else trial_data.position < 0
        self.trials_table.at[self.ntrials, 'response_time'] = trial_data.response_time

        # update psychometrics using online statistics method
        indexer = (trial_data.stim_probability_left, signed_contrast)
        self.psychometrics.loc[indexer, ('count')] += 1
        self.psychometrics.loc[indexer, ('response_time')], self.psychometrics.loc[indexer, ('response_time_std')] = online_std(
            new_sample=trial_data.response_time,
            new_count=self.psychometrics.loc[indexer, ('count')],
            old_mean=self.psychometrics.loc[indexer, ('response_time')],
            old_std=self.psychometrics.loc[indexer, ('response_time_std')],
        )
        self.psychometrics.loc[indexer, ('choice')], self.psychometrics.loc[indexer, ('choice_std')] = online_std(
            new_sample=float(choice),
            new_count=self.psychometrics.loc[indexer, ('count')],
            old_mean=self.psychometrics.loc[indexer, ('choice')],
            old_std=self.psychometrics.loc[indexer, ('choice_std')],
        )
        # update last trials table
        self.last_trials = self.last_trials.shift(-1)
        i = NTRIALS_PLOT - 1
        self.last_trials.at[i, 'correct'] = trial_data.trial_correct
        self.last_trials.at[i, 'signed_contrast'] = signed_contrast
        self.last_trials.at[i, 'stim_on'] = bpod_data['States timestamps']['stim_on'][0][0]
        self.last_trials.at[i, 'play_tone'] = bpod_data['States timestamps']['play_tone'][0][0]
        self.last_trials.at[i, 'reward_time'] = bpod_data['States timestamps']['reward'][0][0]
        self.last_trials.at[i, 'error_time'] = bpod_data['States timestamps']['error'][0][0]
        self.last_trials.at[i, 'response_time'] = trial_data.response_time
        # update rgb image
        self.rgb_background = np.roll(self.rgb_background, -1, axis=0)
        self.rgb_background[-1] = np.array([0, 255, 0]) if trial_data.trial_correct else np.array([255, 0, 0])
        # update contrasts
        self.last_contrasts = np.roll(self.last_contrasts, -1, axis=0)
        self.last_contrasts[-1, :] = 0
        self.last_contrasts[-1, int(self.last_trials.signed_contrast.iloc[-1] > 0)] = abs(
            self.last_trials.signed_contrast.iloc[-1]
        )
        self.ntrials_nan = self.ntrials if self.ntrials > 0 else np.nan
        self.percent_correct = self.ntrials_correct / self.ntrials_nan * 100

    def compute_end_session_criteria(self):
        """
        Implements critera to change the color of the figure display, according to the specifications of the task
        :return:
        """
        colour = {'red': '#eb5757', 'green': '#57eb8b', 'yellow': '#ede34e', 'white': '#ffffff'}
        # Within the first part of the session we don't apply response time criterion
        if self.time_elapsed < ENGAGED_CRITIERION['secs']:
            return colour['white']
        # if the mouse has been training for more than 90 minutes subject training too long
        elif self.time_elapsed > (90 * 60):
            return colour['red']
        # the mouse fails to do more than 400 trials in the first 45 mins
        elif self.ntrials_engaged <= ENGAGED_CRITIERION['trial_count']:
            return colour['green']
        # the subject reaction time over the last 20 trials is more than 5 times greater than the overall reaction time
        elif (self.trials_table['response_time'][: self.ntrials].median() * 5) < self.last_trials['response_time'].median():
            return colour['yellow']
        # 90 > time > 45 min and subject's avg response time hasn't significantly decreased
        else:
            return colour['white']


class OnlinePlots:
    """
    Full object to implement the online plots
    Either the object is instantiated in a static mode from an existing jsonable file and it will produce the figure
    >>> oplt = OnlinePlots(task_file)
    Or it can be instantiated empty, and then run on a file during acquisition.
    Use ctrl + Z to interrupt
    >>> OnlinePlots().run(task_file)
    """

    def __init__(self, task_file=None):
        self.data = DataModel(task_file=task_file)

        # create figure and axes
        h = Bunch({})
        h.fig = plt.figure(constrained_layout=True, figsize=(10, 8))
        self._set_session_string()
        h.fig_title = h.fig.suptitle(f'{self._session_string}')
        nc = 9
        hc = nc // 2
        h.gs = h.fig.add_gridspec(2, nc)
        h.ax_trials = h.fig.add_subplot(h.gs[:, :hc])
        h.ax_psych = h.fig.add_subplot(h.gs[0, hc : nc - 1])
        h.ax_performance = h.fig.add_subplot(h.gs[0, nc - 1])
        h.ax_reaction = h.fig.add_subplot(h.gs[1, hc : nc - 1])
        h.ax_water = h.fig.add_subplot(h.gs[1, nc - 1])

        h.ax_psych.set(title='psychometric curve', xlim=[-1, 1], ylim=[0, 1])
        h.ax_reaction.set(title='reaction times', xlim=[-1, 1], ylim=[0, 4], xlabel='signed contrast')
        xticks = np.arange(-1, 1.1, 0.25)
        xticklabels = np.array([f'{x:g}' for x in xticks])
        xticklabels[1::2] = ''
        h.ax_psych.set_xticks(xticks, xticklabels)
        h.ax_reaction.set_xticks(xticks, xticklabels)

        h.ax_trials.set(yticks=[], title='trials timeline', xlim=[-5, 30], xlabel='time (s)')
        h.ax_trials.set_xticks(h.ax_trials.get_xticks(), [''] + h.ax_trials.get_xticklabels()[1::])
        h.ax_performance.set(xticks=[], xlim=[-0.6, 0.6], ylim=[0, 100], title='performance')
        h.ax_water.set(xticks=[], xlim=[-0.6, 0.6], ylim=[0, 1000], title='reward')

        # create psych curves
        h.curve_psych = {}
        h.curve_reaction = {}
        for p in PROBABILITY_SET:
            h.curve_psych[p] = h.ax_psych.plot(
                self.data.psychometrics.loc[p].index,
                self.data.psychometrics.loc[p]['choice'],
                '.-',
                zorder=10,
                clip_on=False,
                label=f'p = {p}',
            )
            h.curve_reaction[p] = h.ax_reaction.plot(
                self.data.psychometrics.loc[p].index, self.data.psychometrics.loc[p]['response_time'], '.-', label=f'p = {p}'
            )
        h.ax_psych.legend()
        h.ax_reaction.legend()

        # create the two bars on the right side
        h.bar_correct = h.ax_performance.bar(0, self.data.percent_correct, label='correct', color='k')
        h.bar_water = h.ax_water.bar(0, self.data.water_delivered, label='water delivered', color='b')

        # create the trials timeline view in a single axis
        xpos = np.tile([[-3.75, -1.25]], (NTRIALS_PLOT, 1)).T.flatten()
        ypos = np.tile(np.arange(NTRIALS_PLOT), 2)
        h.im_trials = h.ax_trials.imshow(
            self.data.rgb_background, alpha=0.2, extent=[-10, 50, -0.5, NTRIALS_PLOT - 0.5], aspect='auto', origin='lower'
        )
        kwargs = dict(markersize=25, markeredgewidth=2)
        h.lines_trials = {
            'stim_on': h.ax_trials.plot(
                self.data.last_trials.stim_on, np.arange(NTRIALS_PLOT), '|', color='b', **kwargs, label='stim_on'
            ),
            'reward_time': h.ax_trials.plot(
                self.data.last_trials.reward_time, np.arange(NTRIALS_PLOT), '|', color='g', **kwargs, label='reward_time'
            ),
            'error_time': h.ax_trials.plot(
                self.data.last_trials.error_time, np.arange(NTRIALS_PLOT), '|', color='r', **kwargs, label='error_time'
            ),
            'play_tone': h.ax_trials.plot(
                self.data.last_trials.play_tone, np.arange(NTRIALS_PLOT), '|', color='m', **kwargs, label='play_tone'
            ),
        }
        h.scatter_contrast = h.ax_trials.scatter(
            xpos, ypos, s=250, c=self.data.last_contrasts.T.flatten(), alpha=1, marker='o', vmin=0.0, vmax=1, cmap='Greys'
        )
        xticks = np.arange(-1, 1.1, 0.25)
        xticklabels = np.array([f'{x:g}' for x in xticks])
        xticklabels[1::2] = ''
        h.ax_psych.set_xticks(xticks, xticklabels)

        self.h = h
        self.update_titles()
        plt.show(block=False)
        plt.draw()

    def update_titles(self):
        protocol = (self.data.task_settings['PYBPOD_PROTOCOL'] if self.data.task_settings else '').replace('_', r'\_')
        spacer = r'\ \ ·\ \ '
        main_title = (
            r'$\mathbf{' + protocol + rf'{spacer}{self.data.ntrials}\ trials{spacer}time\ elapsed:\ '
            rf'{str(datetime.timedelta(seconds=int(self.data.time_elapsed)))}' + r'}$'
        )
        self.h.fig_title.set_text(main_title + '\n' + self._session_string)
        self.h.ax_water.title.set_text(f'total reward\n{self.data.water_delivered:.1f}μL')
        self.h.ax_performance.title.set_text(f'performance\n{self.data.percent_correct:.0f}%')

    def update_trial(self, trial_data, bpod_data):
        """
        This method updates both the data model and the graphics for an upcoming trial
        :param trial data: pandas record
        :param bpod data: dict interpreted from the bpod json dump
        :return:
        """
        self.data.update_trial(trial_data, bpod_data)
        self.update_graphics(pupdate=trial_data.stim_probability_left)

    def update_graphics(self, pupdate: float | None = None):
        background_color = self.data.compute_end_session_criteria()
        h = self.h
        h.fig.set_facecolor(background_color)
        self.update_titles()
        for p in PROBABILITY_SET:
            if pupdate is not None and p != pupdate:
                continue
            # update psychometric curves
            iok = ~np.isnan(self.data.psychometrics.loc[p]['choice'].values.astype(np.float32))
            xval = self.data.psychometrics.loc[p].index[iok]
            h.curve_psych[p][0].set(xdata=xval, ydata=self.data.psychometrics.loc[p]['choice'][iok])
            h.curve_reaction[p][0].set(xdata=xval, ydata=self.data.psychometrics.loc[p]['response_time'][iok])
            # update the last trials plot
            self.h.im_trials.set_array(self.data.rgb_background)
            for k in ['stim_on', 'reward_time', 'error_time', 'play_tone']:
                h.lines_trials[k][0].set(xdata=self.data.last_trials[k])
            self.h.scatter_contrast.set_array(self.data.last_contrasts.T.flatten())
            # update barplots
            self.h.bar_correct[0].set(height=self.data.percent_correct)
            self.h.bar_water[0].set(height=self.data.water_delivered)

    def _set_session_string(self) -> None:
        if isinstance(self.data.task_settings, dict):
            training_info, _ = get_subject_training_info(
                subject_name=self.data.task_settings['SUBJECT_NAME'],
                task_name=self.data.task_settings['PYBPOD_PROTOCOL'],
                lab=self.data.task_settings['ALYX_LAB'],
            )
            self._session_string = (
                f'subject: {self.data.task_settings["SUBJECT_NAME"]}  ·  '
                f'weight: {self.data.task_settings["SUBJECT_WEIGHT"]}g  ·  '
                f'training phase: {training_info["training_phase"]}  ·  '
                f'stimulus gain: {self.data.task_settings["STIM_GAIN"]}  ·  '
                f'reward amount: {self.data.task_settings["REWARD_AMOUNT_UL"]}µl'
            )
        else:
            self._session_string = ''

    def run(self, task_file: Path | str) -> None:
        """
        This methods is for online use, it will watch for a file in conjunction with an iblrigv8 running task
        :param task_file:
        :return:
        """
        task_file = Path(task_file)
        self.data.get_task_settings(task_file.parent)
        self._set_session_string()
        self.update_titles()
        self.h.fig.canvas.flush_events()
        self.real_time = Bunch({'fseek': 0, 'time_last_check': 0})
        flag_file = task_file.parent.joinpath('new_trial.flag')

        while True:
            self.h.fig.canvas.draw_idle()
            self.h.fig.canvas.flush_events()
            time.sleep(0.4)
            if not plt.fignum_exists(self.h.fig.number):
                break
            if flag_file.exists():
                trial_data, bpod_data = load_task_jsonable(task_file, offset=self.real_time.fseek)
                new_size = task_file.stat().st_size
                for i in np.arange(len(bpod_data)):
                    self.update_trial(trial_data.iloc[i], bpod_data[i])
                self.real_time.fseek = new_size
                self.real_time.time_last_check = time.time()
                flag_file.unlink()
