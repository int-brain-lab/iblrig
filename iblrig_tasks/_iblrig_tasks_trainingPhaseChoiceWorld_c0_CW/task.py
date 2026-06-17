import iblrig.misc
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld_c0_CW.task import Session as TrainingChoiceWorldC0CWSession
from iblrig_tasks._iblrig_tasks_trainingPhaseChoiceWorld.task import Session as TrainingPhaseChoiceWorldSession


class Session(TrainingPhaseChoiceWorldSession, TrainingChoiceWorldC0CWSession):
    """TrainingPhaseChoiceWorld using the pre-8.23.4 zero-contrast convention.

    This variant reproduces the TrainingPhaseChoiceWorld behaviour as it was implemented in IBLRIG versions 8.10.0 - 8.23.3.
    It is identical to the standard TrainingPhaseChoiceWorld in every respect except for the handling of zero-contrast trials.

    In the standard protocol, a zero-contrast stimulus is assigned to a randomly chosen side. In this protocol, zero-contrast
    trials follows a deterministic convention: the stimulus is always placed on the left, and a clockwise turn is therefore the
    rewarded one (see :meth:`next_trial`).

    Use this protocol when you need behaviour that matches subjects trained under the legacy convention - for example to keep a
    cohort consistent with historical data.
    """

    protocol_name = '_iblrig_tasks_trainingPhaseChoiceWorld_c0_CW'


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
