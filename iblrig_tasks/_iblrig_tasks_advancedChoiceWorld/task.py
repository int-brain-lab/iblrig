import inspect
from pathlib import Path
import yaml

from iblrig.base_choice_world import ActiveChoiceWorldSession
import iblrig.misc


class Session(ActiveChoiceWorldSession):
    """
    Advanced Choice World is the ChoiceWorld task using fixed 50/50 probability for the side
    and contrasts defined in the parameters.
    It differs from TraininChoiceWorld in that it does not implement adaptive contrasts or debiasing,
    and it differs from BiasedChoiceWorld in that it does not implement biased blocks.
    """
    protocol_name = "_iblrig_tasks_advancedChoiceWorld"
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    @staticmethod
    def extra_parser():
        """ :return: argparse.parser() """

        # read defaults from task_parameters.yaml
        task_parameters = Path(inspect.getfile(__class__)).parent.joinpath('task_parameters.yaml')
        with open(task_parameters) as f:
            defaults = yaml.safe_load(f)

        parser = super(Session, Session).extra_parser()
        parser.add_argument('--contrast_set_probability_type', option_strings=['--contrast_set_probability_type'],
                            dest='contrast_set_probability_type', default=defaults["CONTRAST_SET_PROBABILITY_TYPE"],
                            type=str, choices=['skew_zero', 'uniform'], help=f'probability type for contrast set '
                            f'(default: {defaults["CONTRAST_SET_PROBABILITY_TYPE"]})')
        parser.add_argument('--probability_left', option_strings=['--probability_left'],
                            dest='probability_left', default=defaults["PROBABILITY_LEFT"], type=float,
                            help=f'probability for stimulus to appear on the left '
                                 f'(default: {defaults["PROBABILITY_LEFT"]:.1f})')
        parser.add_argument('--reward_amount_ul', option_strings=['--reward_amount_ul'],
                            dest='reward_amount_ul', default=defaults["REWARD_AMOUNT_UL"],
                            type=float, help=f'reward amount (default: {defaults["REWARD_AMOUNT_UL"]}μl)')
        parser.add_argument('--stim_gain', option_strings=['--stim_gain'], dest='stim_gain',
                            default=defaults["STIM_GAIN"], type=float, help=f'visual angle/wheel displacement '
                            f'(deg/mm, default: {defaults["STIM_GAIN"]})')
        return parser

    def next_trial(self):
        # update counters
        self.trial_num += 1
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=self.task_params.PROBABILITY_LEFT)


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
