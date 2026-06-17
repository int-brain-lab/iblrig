import numpy as np

from iblrig.choiceworld import draw_training_contrast
from iblrig.misc import get_task_arguments
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession


class Session(TrainingChoiceWorldSession):
    """TrainingChoiceWorld using the pre-8.23.4 zero-contrast convention.

    This variant reproduces the TrainingChoiceWorld behaviour as it was implemented in IBLRIG versions 8.10.0 - 8.23.3.
    It is identical to the standard TrainingChoiceWorld in every respect except for the handling of zero-contrast trials.

    In the standard protocol, a zero-contrast stimulus is assigned to a randomly chosen side. In this protocol, zero-contrast
    trials follows a deterministic convention: the stimulus is always placed on the left, and a clockwise turn is therefore the
    rewarded one (see :meth:`next_trial`).

    Use this protocol when you need behaviour that matches subjects trained under the legacy convention - for example to keep a
    cohort consistent with historical data.
    """

    protocol_name = '_iblrig_tasks_trainingChoiceWorld_c0_CW'

    def next_trial(self):
        # update counters
        self.trial_num += 1
        self.var['training_phase_trial_counts'][self.training_phase] += 1

        # check if the subject graduates to a new training phase
        self.check_training_phase()

        # draw the next trial
        signed_contrast = draw_training_contrast(self.training_phase)
        position = self.task_params.STIM_POSITIONS[int(np.sign(signed_contrast) == 1)]
        contrast = np.abs(signed_contrast)

        # debiasing: if the previous trial was incorrect, not a no-go and easy
        if self.task_params.DEBIAS and self.trial_num >= 1 and self.training_phase < 5:
            last_contrast = self.trials_table.loc[self.trial_num - 1, 'contrast']
            do_debias_trial = (
                (self.trials_table.loc[self.trial_num - 1, 'trial_correct'] != 1)
                and (self.trials_table.loc[self.trial_num - 1, 'response_side'] != 0)
                and last_contrast >= 0.5
            )
            self.trials_table.at[self.trial_num, 'debias_trial'] = do_debias_trial
            if do_debias_trial:
                # indices of trials that had a response
                iresponse = np.logical_and(self.trials_table['response_side'].notna(), self.trials_table['response_side'] != 0)
                iresponse = iresponse.index[iresponse]

                # takes the average of right responses over last 10 response trials
                average_right = (self.trials_table['response_side'][iresponse[-np.minimum(10, iresponse.size) :]] == 1).mean()

                # the probability of the next stimulus being on the left is a draw from a normal distribution centered
                # on the average right with sigma 0.5 - if it is less than 0.5 the next stimulus will be on the left.
                position = self.task_params.STIM_POSITIONS[int(np.random.normal(average_right, 0.5) >= 0.5)]

                # contrast is the last contrast
                contrast = last_contrast
        else:
            self.trials_table.at[self.trial_num, 'debias_trial'] = False

        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=self.task_params.PROBABILITY_LEFT, position=position, contrast=contrast)
        self.trials_table.at[self.trial_num, 'training_phase'] = self.training_phase


if __name__ == '__main__':  # pragma: no cover
    kwargs = get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
