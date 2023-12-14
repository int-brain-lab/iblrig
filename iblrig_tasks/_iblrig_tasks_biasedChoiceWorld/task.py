import iblrig.misc
from iblrig.base_choice_world import BiasedChoiceWorldSession


class Session(BiasedChoiceWorldSession):
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
