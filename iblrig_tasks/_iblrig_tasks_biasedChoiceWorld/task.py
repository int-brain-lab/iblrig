import iblrig.misc
from iblrig.base_choice_world import BiasedChoiceWorldSession


class Session(BiasedChoiceWorldSession): ...


if __name__ == '__main__':  # pragma: no cover
    kwargs = BiasedChoiceWorldSession.ArgumentsModel().model_dump()
    # kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    # sess = Session(**kwargs)
    # sess.run()
