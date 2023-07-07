import logging
from iblrig.base_choice_world import ActiveChoiceWorldSession
import iblrig.misc

log = logging.getLogger("iblrig")


class Session(ActiveChoiceWorldSession):
    protocol_name = "_iblrig_tasks_advancedChoiceWorld"

    def next_trial(self):
        # update counters
        self.trial_num += 1
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=0.5)


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments()
    sess = Session(**kwargs)
    sess.run()
