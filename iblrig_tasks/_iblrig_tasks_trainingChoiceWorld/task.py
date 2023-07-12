import argparse
from iblrig.base_choice_world import TrainingChoiceWorldSession
import iblrig.misc


class Session(TrainingChoiceWorldSession):

    @staticmethod
    def extra_parser():
        """ :return: argparse.parser() """
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--training_phase', option_strings=['--training_phase'], dest='training_phase', default=0, type=int)
        return parser


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
