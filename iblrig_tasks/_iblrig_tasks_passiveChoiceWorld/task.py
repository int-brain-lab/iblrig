import datetime
import logging

from iblrig.base_choice_world import ChoiceWorldSession
import iblrig.test

log = logging.getLogger("iblrig")


class Session(ChoiceWorldSession):
    protocol_name = "_iblrig_tasks_passiveChoiceWorld"

    def __init__(self, duration_secs=None, **kwargs):
        super(ChoiceWorldSession, self).__init__(**kwargs)

    def run(self):
        """
        This is the method that runs the task with the actual state machine
        :return:
        """
        # super(ChoiceWorldSession, self).run()
        log.info("Starting passive protocol")
        import time
        while True:
            time.sleep(1.5)
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break
        log.critical("Graceful exit")
        self.session_info.SESSION_END_TIME = datetime.datetime.now().isoformat()
        self.save_task_parameters_to_json_file()
        self.register_to_alyx()


if __name__ == "__main__":
    # python .\iblrig_tasks\_iblrig_tasks_spontaneous\task.py --subject mysubject
    kwargs = iblrig.misc.get_task_runner_argument_parser()
    sess = Session(**kwargs)
    sess.run()
