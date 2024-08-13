from iblrig.base_choice_world import BiasedChoiceWorldSession
from iblrig.misc import get_task_arguments, truncated_exponential


class Session(BiasedChoiceWorldSession):
    protocol_name = '_iblrig_tasks_imagingChoiceWorld'

    @staticmethod
    def draw_quiescent_period() -> float:
        """
        Draw the quiescent period.

        For this task we double the quiescence period texp draw and remove the absolute offset of 200ms.
        The resulting is a truncated exp distribution between 400ms and 1 sec

        TODO: This is a broken overload and never actually called - quiescent periods are not changed from BiasedCW
        """
        return truncated_exponential(scale=0.35 * 2, min_value=0.2 * 2, max_value=0.5 * 2)


if __name__ == '__main__':  # pragma: no cover
    kwargs = get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
