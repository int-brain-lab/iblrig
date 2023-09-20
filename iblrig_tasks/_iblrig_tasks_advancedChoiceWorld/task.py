from iblrig.base_choice_world import ActiveChoiceWorldSession
import iblrig.misc


class Session(ActiveChoiceWorldSession):
    protocol_name = "_iblrig_tasks_advancedChoiceWorld"
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    def next_trial(self):
        # update counters
        self.trial_num += 1
        # save and send trial info to bonsai
        self.draw_next_trial_info(pleft=0.5)


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
