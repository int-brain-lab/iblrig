from pathlib import Path

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
    It differs from TraininChoiceWorld in that it does not implement adaptive contrasts or debiasing,
    and it differs from BiasedChoiceWorld in that it does not implement biased blocks.
    """

    protocol_name = '_iblrig_tasks_advancedChoiceWorld'
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    def __init__(
        self,
        *args,
        contrast_set: list[float] = DEFAULTS['CONTRAST_SET'],
        contrast_set_probability_type: str = DEFAULTS['CONTRAST_SET_PROBABILITY_TYPE'],
        probability_left: float = DEFAULTS['PROBABILITY_LEFT'],
        reward_amount_ul: float = DEFAULTS['REWARD_AMOUNT_UL'],
        stim_gain: float = DEFAULTS['STIM_GAIN'],
        **kwargs,
    ):
        super(Session, self).__init__(*args, **kwargs)
        self.task_params['CONTRAST_SET'] = contrast_set
        self.task_params['CONTRAST_SET_PROBABILITY_TYPE'] = contrast_set_probability_type
        self.task_params['PROBABILITY_LEFT'] = probability_left
        self.task_params['REWARD_AMOUNT_UL'] = reward_amount_ul
        self.task_params['STIM_GAIN'] = stim_gain

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
            help='set of contrasts to present',
        )
        parser.add_argument(
            '--contrast_set_probability_type',
            option_strings=['--contrast_set_probability_type'],
            dest='contrast_set_probability_type',
            default=DEFAULTS['CONTRAST_SET_PROBABILITY_TYPE'],
            type=str,
            choices=['skew_zero', 'uniform'],
            help=f'probability type for contrast set ' f'(default: {DEFAULTS["CONTRAST_SET_PROBABILITY_TYPE"]})',
        )
        parser.add_argument(
            '--probability_left',
            option_strings=['--probability_left'],
            dest='probability_left',
            default=DEFAULTS['PROBABILITY_LEFT'],
            type=float,
            help=f'probability for stimulus to appear on the left ' f'(default: {DEFAULTS["PROBABILITY_LEFT"]:.1f})',
        )
        parser.add_argument(
            '--reward_amount_ul',
            option_strings=['--reward_amount_ul'],
            dest='reward_amount_ul',
            default=DEFAULTS['REWARD_AMOUNT_UL'],
            type=float,
            help=f'reward amount (default: {DEFAULTS["REWARD_AMOUNT_UL"]}μl)',
        )
        parser.add_argument(
            '--stim_gain',
            option_strings=['--stim_gain'],
            dest='stim_gain',
            default=DEFAULTS['STIM_GAIN'],
            type=float,
            help=f'visual angle/wheel displacement ' f'(deg/mm, default: {DEFAULTS["STIM_GAIN"]})',
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
