"""
The ephys choice world task is the same as the biased choice world except that
the trials are pregenerated and saved in a fixture file.
"""
import logging
from pathlib import Path

import pandas as pd

from iblrig.base_choice_world import BiasedChoiceWorldSession
import iblrig.misc

log = logging.getLogger("iblrig")


class Session(BiasedChoiceWorldSession):
    pregenerated_session_index = 10

    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        trials_table = pd.read_parquet(Path(__file__).parent.joinpath('trials_fixtures.pqt'))
        self.trials_table = trials_table.loc[
            trials_table['session_id'] == self.pregenerated_session_index].reindex().drop(columns=['session_id'])
        self.trials_table = self.trials_table.reset_index()
        # reconstruct the block dataframe from the trials table
        self.blocks_table = self.trials_table.groupby('block_num').agg(
            probability_left=pd.NamedAgg(column="stim_probability_left", aggfunc="first"),
            block_length=pd.NamedAgg(column="stim_probability_left", aggfunc="count"),
        )


if __name__ == "__main__":  # pragma: no cover
    kwargs = iblrig.misc.get_task_runner_argument_parser()
    sess = Session(**kwargs)
    sess.run()
