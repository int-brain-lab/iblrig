import argparse
import logging
from iblrig.base_choice_world import TrainingChoiceWorldSession
import iblrig.misc

log = logging.getLogger("iblrig")

# todo online plotting for trial stops


class Session(TrainingChoiceWorldSession):
    pass


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--training_phase', option_strings=['--training_phase'], dest='training_phase', default=0, type=int)
    kwargs = iblrig.misc.get_task_arguments(parents=[parser])
    sess = Session(**kwargs)
    sess.run()
