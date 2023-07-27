import iblrig.misc
from iblrig.base_choice_world import BiasedChoiceWorldSession


class Session(BiasedChoiceWorldSession):
    protocol_name = "_iblrig_tasks_imagingChoiceWorld"
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials']

    def draw_quiescent_period(self):
        """
        For this task we double the quiescence period texp draw and remove the absolute
        offset of 200ms. The resulting is a truncated exp distribution between 400ms and 1 sec
        """
        return iblrig.misc.texp(factor=0.35 * 2, min_=0.2 * 2, max_=0.5 * 2)


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments()
    sess = Session(**kwargs)
    sess.run()
