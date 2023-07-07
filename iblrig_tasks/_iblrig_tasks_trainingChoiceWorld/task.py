import logging
from iblrig.base_choice_world import TrainingChoiceWorldSession
import iblrig.misc

log = logging.getLogger("iblrig")

# todo online plotting for trial stops


class Session(TrainingChoiceWorldSession):
    pass


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_runner_argument_parser()
    training_phase = 0
    if kwargs['subject'] == 'ZFM-05923':
        training_phase = 5
    if kwargs['subject'] == 'ZFM-06440':
        training_phase = 0
    sess = Session(training_phase=training_phase, **kwargs)
    sess.run()
