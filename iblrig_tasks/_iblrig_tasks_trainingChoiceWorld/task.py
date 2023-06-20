import logging
from iblrig.base_choice_world import TrainingChoiceWorldSession
import iblrig.misc

log = logging.getLogger("iblrig")

# todo online plotting for trial stops


class Session(TrainingChoiceWorldSession):
    pass


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_runner_argument_parser()
    sess = Session(**kwargs)
    sess.run()
