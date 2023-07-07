"""
The ephys choice world task is the same as the biased choice world except that
the trials are pregenerated and saved in a fixture file.
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

from iblrig.base_choice_world import BiasedChoiceWorldSession
import iblrig.misc

log = logging.getLogger("iblrig")


class Session(BiasedChoiceWorldSession):

    def __init__(self, *args, session_template_id=0, delay__secs=0, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.session_template_id = session_template_id
        trials_table = pd.read_parquet(Path(__file__).parent.joinpath('trials_fixtures.pqt'))
        self.trials_table = trials_table.loc[
            trials_table['session_id'] == self.session_template_id].reindex().drop(columns=['session_id'])
        self.trials_table = self.trials_table.reset_index()
        # reconstruct the block dataframe from the trials table
        self.blocks_table = self.trials_table.groupby('block_num').agg(
            probability_left=pd.NamedAgg(column="stim_probability_left", aggfunc="first"),
            block_length=pd.NamedAgg(column="stim_probability_left", aggfunc="count"),
        )
        self.task_params.SESSION_START_DELAY_SEC = delay__secs


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--session_template_id', option_strings=['--session_template_id'],
                        dest='session_template_id', default=0, type=int)
    parser.add_argument('--delay_secs', option_strings=['--delay_secs'], dest='delay_secs', default=0, type=int)
    kwargs = iblrig.misc.get_task_arguments(parents=[parser])
    sess = Session(**kwargs)
    sess.run()
