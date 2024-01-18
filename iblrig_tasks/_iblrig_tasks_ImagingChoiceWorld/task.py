import iblrig.misc
from iblrig.base_choice_world import BiasedChoiceWorldSession


class Session(BiasedChoiceWorldSession):
    protocol_name = '_iblrig_tasks_imagingChoiceWorld'
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials']

    def draw_quiescent_period(self):
        """
        For this task we double the quiescence period texp draw and remove the absolute
        offset of 200ms. The resulting is a truncated exp distribution between 400ms and 1 sec
        """
        return iblrig.misc.truncated_exponential(factor=0.35 * 2, min_value=0.2 * 2, max_value=0.5 * 2)


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
