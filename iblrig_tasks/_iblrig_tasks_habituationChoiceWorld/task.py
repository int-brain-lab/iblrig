import iblrig.misc
from iblrig.base_choice_world import HabituationChoiceWorldSession


class Session(HabituationChoiceWorldSession):
    extractor_tasks = ['TrialRegisterRaw', 'HabituationTrials']


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
