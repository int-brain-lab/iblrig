import iblrig.misc
from iblrig.base_choice_world import TrainingChoiceWorldSession

TRAINING_PHASE = -1
ADAPTIVE_REWARD = -1.0


class Session(TrainingChoiceWorldSession):
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    @staticmethod
    def extra_parser():
        """:return: argparse.parser()"""
        parser = super(Session, Session).extra_parser()
        parser.add_argument(
            '--training_phase',
            option_strings=['--training_phase'],
            dest='training_phase',
            default=TRAINING_PHASE,
            type=int,
            help='defines the set of contrasts presented to the subject',
        )
        parser.add_argument(
            '--adaptive_reward',
            option_strings=['--adaptive_reward'],
            dest='adaptive_reward',
            default=ADAPTIVE_REWARD,
            type=float,
            help='reward volume in microliters',
        )
        parser.add_argument(
            '--adaptive_gain',
            option_strings=['--adaptive_gain'],
            dest='adaptive_gain',
            default=None,
            type=float,
            help='Gain of the wheel in degrees/mm',
        )
        return parser


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
