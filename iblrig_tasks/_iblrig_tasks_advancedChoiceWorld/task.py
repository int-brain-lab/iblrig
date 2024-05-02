from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import iblrig.misc
from iblrig.base_choice_world import ActiveChoiceWorldSession

# read defaults from task_parameters.yaml
with open(Path(__file__).parent.joinpath('task_parameters.yaml')) as f:
    DEFAULTS = yaml.safe_load(f)


class Session(ActiveChoiceWorldSession):
    """
    Advanced Choice World is the ChoiceWorld task using fixed 50/50 probability for the side
    and contrasts defined in the parameters.
    It differs from TrainingChoiceWorld in that it does not implement adaptive contrasts or debiasing,
    and it differs from BiasedChoiceWorld in that it does not implement biased blocks.
    """

    protocol_name = '_iblrig_tasks_advancedChoiceWorld'

    def __init__(
        self,
        *args,
        contrast_set: list[float] = DEFAULTS['CONTRAST_SET'],
        probability_set: list[float] = DEFAULTS['PROBABILITY_SET'],
        reward_set_ul: list[float] = DEFAULTS['REWARD_SET_UL'],
        position_set: list[float] = DEFAULTS['POSITION_SET'],
        stim_gain: float = DEFAULTS['STIM_GAIN'],
        **kwargs,
    ):
        task_parameters_overload = {
            'CONTRAST_SET': contrast_set,
            'PROBABILITY_SET': probability_set,
            'REWARD_SET_UL': reward_set_ul,
            'POSITION_SET': position_set,
            'STIM_GAIN': stim_gain,
            'STIM_POSITIONS': sorted(list(set(position_set))),
        }
        super().__init__(*args, task_parameters_overload=task_parameters_overload, **kwargs)
        nc = len(contrast_set)
        assert len(probability_set) in [nc, 1], 'probability_set must be a scalar or have the same length as contrast_set'
        assert len(reward_set_ul) in [nc, 1], 'reward_set_ul must be a scalar or have the same length as contrast_set'
        assert len(position_set) == nc, 'position_set must have the same length as contrast_set'
        # it is easier to work with parameters as a dataframe
        self.df_contingencies = pd.DataFrame(columns=['contrast', 'probability', 'reward_amount_ul', 'position'])
        self.df_contingencies['contrast'] = contrast_set
        self.df_contingencies['probability'] = probability_set if len(probability_set) == nc else probability_set[0]
        self.df_contingencies['reward_amount_ul'] = reward_set_ul if len(reward_set_ul) == nc else reward_set_ul[0]
        self.df_contingencies['position'] = position_set
        # normalize the probabilities
        self.df_contingencies.loc[:, 'probability'] = self.df_contingencies.loc[:, 'probability'] / np.sum(
            self.df_contingencies.loc[:, 'probability']
        )
        # update the PROBABILITY LEFT field to reflect the probabilities in the parameters above
        self.task_params['PROBABILITY_LEFT'] = np.sum(
            self.df_contingencies['probability'] * (self.df_contingencies['position'] < 0)
        )

    def draw_next_trial_info(self, **kwargs):
        nc = self.df_contingencies.shape[0]
        ic = np.random.choice(np.arange(nc), p=self.df_contingencies['probability'])
        # now calling the super class with the proper parameters
        super().draw_next_trial_info(
            pleft=self.task_params.PROBABILITY_LEFT,
            contrast=self.df_contingencies.at[ic, 'contrast'],
            position=self.df_contingencies.at[ic, 'position'],
            reward_amount=self.df_contingencies.at[ic, 'reward_amount_ul'],
        )

    @property
    def reward_amount(self):
        return self.task_params.REWARD_AMOUNTS_UL[0]

    @staticmethod
    def extra_parser():
        """:return: argparse.parser()"""
        parser = super(Session, Session).extra_parser()
        parser.add_argument(
            '--contrast_set',
            option_strings=['--contrast_set'],
            dest='contrast_set',
            default=DEFAULTS['CONTRAST_SET'],
            nargs='+',
            type=float,
            help='Contrast for each contingency',
        )
        parser.add_argument(
            '--probability_set',
            option_strings=['--probability_set'],
            dest='probability_set',
            default=DEFAULTS['PROBABILITY_SET'],
            nargs='+',
            type=float,
            help='Probabilities of each contingency. If scalar all contingencies are equiprobable',
        )
        parser.add_argument(
            '--reward_set_ul',
            option_strings=['--reward_set_ul'],
            dest='reward_set_ul',
            default=DEFAULTS['REWARD_SET_UL'],
            nargs='+',
            type=float,
            help=f'Reward for each contingency.',
        )
        parser.add_argument(
            '--position_set',
            option_strings=['--position_set'],
            dest='position_set',
            default=DEFAULTS['POSITION_SET'],
            nargs='+',
            type=float,
            help='Position for each contingency in degrees.',
        )
        parser.add_argument(
            '--stim_gain',
            option_strings=['--stim_gain'],
            dest='stim_gain',
            default=DEFAULTS['STIM_GAIN'],
            type=float,
            help=f'Visual angle/wheel displacement ' f'(deg/mm, default: {DEFAULTS["STIM_GAIN"]})',
        )
        return parser

    def next_trial(self):
        # update counters
        self.trial_num += 1
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=self.task_params.PROBABILITY_LEFT)


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
