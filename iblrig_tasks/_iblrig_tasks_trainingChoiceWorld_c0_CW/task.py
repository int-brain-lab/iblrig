import numpy as np

from iblrig.misc import get_task_arguments
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession


class Session(TrainingChoiceWorldSession):
    """TrainingChoiceWorld using the pre-8.23.4 zero-contrast convention.

    This variant reproduces the TrainingChoiceWorld behaviour as it was implemented in IBLRIG versions 8.10.0 - 8.23.3.
    It is identical to the standard TrainingChoiceWorld in every respect except for the handling of zero-contrast trials.

    In the standard protocol, a zero-contrast stimulus is assigned to a randomly chosen side. In this protocol, zero-contrast
    trials follow a deterministic convention: the stimulus is always placed on the left, and a clockwise turn is therefore the
    rewarded one (see :meth:`_map_signed_contrast_to_position`).

    Use this protocol when you need behaviour that matches subjects trained under the legacy convention - for example to keep a
    cohort consistent with historical data.
    """

    protocol_name = '_iblrig_tasks_trainingChoiceWorld_c0_CW'

    def _map_signed_contrast_to_position(self, signed_contrast: float) -> int:
        """Map a signed contrast to a stimulus position.

        For zero contrasts the stimulus is always placed on the left and rewarded by a clockwise turn.
        """
        return self.task_params.STIM_POSITIONS[int(np.sign(signed_contrast) == 1)]


if __name__ == '__main__':  # pragma: no cover
    kwargs = get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
