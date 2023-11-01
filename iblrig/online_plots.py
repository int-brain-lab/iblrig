from pathlib import Path
import datetime
import time

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pandas.api.types import CategoricalDtype

import one.alf.io
from iblrig.raw_data_loaders import load_task_jsonable
from iblutil.util import Bunch


NTRIALS_INIT = 2000
NTRIALS_PLOT = 20  # do not edit - this is used also to enforce the completion criteria
CONTRAST_SET = np.array([0, 1 / 16, 1 / 8, 1 / 4, 1 / 2, 1])
PROBABILITY_SET = np.array([.2, .5, .8])
# if the mouse does less than 400 trials in the first 45mins it's disengaged
ENGAGED_CRITIERION = {'secs': 45 * 60, 'trial_count': 400}
sns.set_style('white')


class DataModel(object):
    """
    The data model is a pure numpy / pandas container for the choice world task.
    It contains:
    - a psychometrics dataframe that contains the count / choice and response time
    per signed contrast and block contingency
    - a last trials dataframe that contains 20 trials worth of data for the timeline view
    - various counters such as ntrials and water delivered
    """
    def __init__(self, task_file):
        """
        Can be instantiated empty or from an existing jsonable file from any rig version
        :param task_file:
        """
        self.session_path = one.alf.files.get_session_path(task_file) or ""
        self.last_trials = pd.DataFrame(
            columns=['correct', 'signed_contrast', 'stim_on', 'play_tone', 'reward_time', 'error_time', 'response_time'],
            index=np.arange(NTRIALS_PLOT))
        if task_file is None or not Path(task_file).exists():
            self.psychometrics = pd.DataFrame(
                columns=['count', 'response_time', 'choice', 'response_time_std', 'choice_std'],
                index=pd.MultiIndex.from_product([PROBABILITY_SET, np.r_[- np.flipud(CONTRAST_SET[1:]), CONTRAST_SET]])
            )
            self.psychometrics['count'] = 0
            self.trials_table = pd.DataFrame(columns=['response_time'], index=np.arange(NTRIALS_INIT))
            self.ntrials = 0
            self.ntrials_correct = 0
            self.water_delivered = 0
            self.time_elapsed = 0
            self.ntrials_engaged = 0  # those are the trials happening within the first 400s
        else:
            trials_table, bpod_data = load_task_jsonable(task_file)
            # here we take the end time of the first trial as reference to avoid factoring in the delay
            self.time_elapsed = bpod_data[-1]['Trial end timestamp'] - bpod_data[0]['Trial end timestamp']
            trials_table['signed_contrast'] = np.sign(trials_table['position']) * trials_table['contrast']
            trials_table['choice'] = trials_table['position'] > 0
            trials_table.loc[~trials_table.trial_correct, 'choice'] = ~trials_table['choice'][~trials_table.trial_correct]
            trials_table['contrast'] = trials_table['contrast'].astype(
                CategoricalDtype(categories=np.unique(np.r_[-CONTRAST_SET, CONTRAST_SET]), ordered=True))
            trials_table['stim_probability_left'] = trials_table['stim_probability_left'].astype(
                CategoricalDtype(categories=PROBABILITY_SET, ordered=True))
            self.psychometrics = trials_table.groupby(['stim_probability_left', 'signed_contrast']).agg(
                count=pd.NamedAgg(column="signed_contrast", aggfunc="count"),
                response_time=pd.NamedAgg(column="response_time", aggfunc=np.nanmean),
                choice=pd.NamedAgg(column="choice", aggfunc="mean"),
                response_time_std=pd.NamedAgg(column="response_time", aggfunc=np.nanstd),
                choice_std=pd.NamedAgg(column="choice", aggfunc=np.nanmean),
            )
            self.ntrials = trials_table.shape[0]
            self.ntrials_correct = np.sum(trials_table.trial_correct)
            # agg.water_delivered = trials_table.water_delivered.iloc[-1]
            self.water_delivered = trials_table.reward_amount.sum()
            # init the last trials table
            it = self.last_trials.index[-np.minimum(self.ntrials, NTRIALS_PLOT):]
            self.last_trials.loc[it, 'correct'] = trials_table.trial_correct.iloc[-NTRIALS_PLOT:].values
            self.last_trials.loc[it, 'signed_contrast'] = trials_table.signed_contrast.iloc[-NTRIALS_PLOT:].values
            self.last_trials.loc[it, 'response_time'] = trials_table.response_time.iloc[-NTRIALS_PLOT:].values
            self.last_trials.loc[it, 'stim_on'] = np.array(
                [bpod_data[i]['States timestamps']['stim_on'][0][0] for i in np.arange(-it.size, 0)])
            self.last_trials.loc[it, 'play_tone'] = np.array(
                [bpod_data[i]['States timestamps']['play_tone'][0][0] for i in np.arange(-it.size, 0)])
            self.last_trials.loc[it, 'reward_time'] = np.array(
                [bpod_data[i]['States timestamps']['reward'][0][0] for i in np.arange(-it.size, 0)])
            self.last_trials.loc[it, 'error_time'] = np.array(
                [bpod_data[i]['States timestamps']['error'][0][0] for i in np.arange(-it.size, 0)])
            # we keep only a single column as buffer
            self.trials_table = trials_table[['response_time']]
        # for the trials plots this is the background image showing green if correct, red if incorrect
        self.rgb_background = np.zeros((NTRIALS_PLOT, 1, 3), dtype=np.uint8)
        self.rgb_background[self.last_trials.correct == False, 0, 0] = 255  # noqa
        self.rgb_background[self.last_trials.correct == True, 0, 1] = 255  # noqa
        # keep the last contrasts as a 20 by 2 array
        ileft = np.where(self.last_trials.signed_contrast < 0)[0]  # negative position is left
        iright = np.where(self.last_trials.signed_contrast > 0)[0]
        self.last_contrasts = np.zeros((NTRIALS_PLOT, 2))
        self.last_contrasts[ileft, 0] = np.abs(self.last_trials.signed_contrast[ileft])
        self.last_contrasts[iright, 1] = np.abs(self.last_trials.signed_contrast[iright])

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
            old_std=self.psychometrics.loc[indexer, ('response_time_std')]
        )
        self.psychometrics.loc[indexer, ('choice')], self.psychometrics.loc[indexer, ('choice_std')] = online_std(
            new_sample=float(choice),
            new_count=self.psychometrics.loc[indexer, ('count')],
            old_mean=self.psychometrics.loc[indexer, ('choice')],
            old_std=self.psychometrics.loc[indexer, ('choice_std')]
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
            self.last_trials.signed_contrast.iloc[-1])

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
        elif (self.trials_table['response_time'][:self.ntrials].median() * 5) < self.last_trials['response_time'].median():
            return colour['yellow']
        # 90 > time > 45 min and subject's avg response time hasn't significantly decreased
        else:
            return colour['white']


class OnlinePlots(object):
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
        h.fig_title = h.fig.suptitle(f"{self._session_string}", fontweight='bold')
        nc = 9
        hc = nc // 2
        h.gs = h.fig.add_gridspec(2, nc)
        h.ax_trials = h.fig.add_subplot(h.gs[:, :hc])
        h.ax_psych = h.fig.add_subplot(h.gs[0, hc:nc - 1])
        h.ax_performance = h.fig.add_subplot(h.gs[0, nc - 1])
        h.ax_reaction = h.fig.add_subplot(h.gs[1, hc:nc - 1])
        h.ax_water = h.fig.add_subplot(h.gs[1, nc - 1])
        h.ax_psych.set(title='psychometric curve', xlim=[-1.01, 1.01], ylim=[0, 1.01])
        h.ax_reaction.set(title='reaction times', xlim=[-1.01, 1.01], ylim=[0, 4], xlabel='signed contrast')
        h.ax_trials.set(yticks=[], title='trials timeline', xlim=[-5, 30], xlabel='time (s)')
        h.ax_performance.set(xticks=[], xlim=[-1.01, 1.01], title='# trials')
        h.ax_water.set(xticks=[], xlim=[-1.01, 1.01], ylim=[0, 1000], title='water (uL)')

        # create psych curves
        h.curve_psych = {}
        h.curve_reaction = {}
        for i, p in enumerate(PROBABILITY_SET):
            h.curve_psych[p] = h.ax_psych.plot(
                self.data.psychometrics.loc[p].index, self.data.psychometrics.loc[p]['choice'], '.-')
            h.curve_reaction[p] = h.ax_reaction.plot(
                self.data.psychometrics.loc[p].index, self.data.psychometrics.loc[p]['response_time'], '.-')

        # create the two bars on the right side
        h.bar_correct = h.ax_performance.bar(0, self.data.ntrials_correct, label='correct', color='g')
        h.bar_error = h.ax_performance.bar(
            0, self.data.ntrials - self.data.ntrials_correct, label='error', color='r', bottom=self.data.ntrials_correct)
        h.bar_water = h.ax_water.bar(0, self.data.water_delivered, label='water delivered', color='b')

        # create the trials timeline view in a single axis
        xpos = np.tile([[-4, -1.5]], (NTRIALS_PLOT, 1)).T.flatten()
        ypos = np.tile(np.arange(NTRIALS_PLOT), 2)
        h.im_trials = h.ax_trials.imshow(
            self.data.rgb_background, alpha=.2, extent=[-10, 50, -.5, NTRIALS_PLOT - .5], aspect='auto', origin='lower')
        kwargs = dict(markersize=25, markeredgewidth=2)
        h.lines_trials = {
            'stim_on': h.ax_trials.plot(
                self.data.last_trials.stim_on, np.arange(NTRIALS_PLOT), '|', color='b', **kwargs, label='stim_on'),
            'reward_time': h.ax_trials.plot(
                self.data.last_trials.reward_time, np.arange(NTRIALS_PLOT), '|', color='g', **kwargs, label='reward_time'),
            'error_time': h.ax_trials.plot(
                self.data.last_trials.error_time, np.arange(NTRIALS_PLOT), '|', color='r', **kwargs, label='error_time'),
            'play_tone': h.ax_trials.plot(
                self.data.last_trials.play_tone, np.arange(NTRIALS_PLOT), '|', color='m', **kwargs, label='play_tone'),
        }
        h.scatter_contrast = h.ax_trials.scatter(xpos, ypos, s=250, c=self.data.last_contrasts.T.flatten(),
                                                 alpha=1, marker='o', vmin=0.0, vmax=1, cmap='Greys')
        self.h = h
        self.update_titles()
        plt.show(block=False)
        plt.draw()

    def update_titles(self):
        self.h.fig_title.set_text(
            f"{self._session_string} time elapsed: {str(datetime.timedelta(seconds=int(self.data.time_elapsed)))}")
        self.h.ax_water.title.set_text(f"water \n {self.data.water_delivered:.2f} (uL)")
        self.h.ax_performance.title.set_text(f" correct/tot \n {self.data.ntrials_correct} / {self.data.ntrials}")

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
            self.h.bar_correct[0].set(height=self.data.ntrials_correct)
            self.h.bar_error[0].set(height=self.data.ntrials - self.data.ntrials_correct, y=self.data.ntrials_correct)
            self.h.bar_water[0].set(height=self.data.water_delivered)
            h.ax_performance.set(ylim=[0, (self.data.ntrials // 50 + 1) * 50])

    @property
    def _session_string(self) -> str:
        return ' - '.join(self.data.session_path.parts[-3:]) if self.data.session_path != "" else ""

    def run(self, task_file: Path | str) -> None:
        """
        This methods is for online use, it will watch for a file in conjunction with an iblrigv8 running task
        :param task_file:
        :return:
        """
        self.h.fig.canvas.flush_events()
        self.real_time = Bunch({'fseek': 0, 'time_last_check': 0})
        task_file = Path(task_file)
        flag_file = task_file.parent.joinpath('new_trial.flag')

        while True:
            self.h.fig.canvas.draw_idle()
            self.h.fig.canvas.flush_events()
            time.sleep(.4)
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
