import iblrig.misc
from iblrig.base_choice_world import BiasedChoiceWorldSession


class Session(BiasedChoiceWorldSession): ...


if __name__ == '__main__':  # pragma: no cover
    settings = BiasedChoiceWorldSession.get_settings_dict()
    # kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    # sess = Session(**kwargs)
    # sess.run()
