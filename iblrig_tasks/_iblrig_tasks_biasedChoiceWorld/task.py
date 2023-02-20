import logging
from iblrig.base_choice_world import BiasedChoiceWorldSession as Session
import iblrig.misc

log = logging.getLogger("iblrig")


if __name__ == "__main__":
    kwargs = iblrig.misc.get_task_runner_argument_parser()
    sess = Session(**kwargs)
    sess.run()
