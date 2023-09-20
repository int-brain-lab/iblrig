from iblrig.base_choice_world import TrainingChoiceWorldSession
import iblrig.misc


class Session(TrainingChoiceWorldSession):
    protocol_name = "_iblrig_tasks_trainingPhaseChoiceWorld"
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.training_phase = self.task_params["TRAINING_PHASE"]

    def check_training_phase(self):
        pass


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
