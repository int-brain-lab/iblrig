"""
The ephys choice world task is the same as the biased choice world except that
the trials are pregenerated and saved in a fixture file.
"""
from pathlib import Path

import pandas as pd

import iblrig.misc
from iblrig.base_choice_world import BiasedChoiceWorldSession


class Session(BiasedChoiceWorldSession):
    protocol_name = '_iblrig_tasks_ephysChoiceWorld'
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    def __init__(self, *args, session_template_id=0, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.task_params.SESSION_TEMPLATE_ID = session_template_id
        trials_table = pd.read_parquet(Path(__file__).parent.joinpath('trials_fixtures.pqt'))
        self.trials_table = (
            trials_table.loc[trials_table['session_id'] == session_template_id].reindex().drop(columns=['session_id'])
        )
        self.trials_table = self.trials_table.reset_index()
        # reconstruct the block dataframe from the trials table
        self.blocks_table = self.trials_table.groupby('block_num').agg(
            probability_left=pd.NamedAgg(column='stim_probability_left', aggfunc='first'),
            block_length=pd.NamedAgg(column='stim_probability_left', aggfunc='count'),
        )

    @staticmethod
    def extra_parser():
        """:return: argparse.parser()"""
        parser = super(Session, Session).extra_parser()
        parser.add_argument(
            '--session_template_id',
            option_strings=['--session_template_id'],
            dest='session_template_id',
            default=0,
            type=int,
            help='pre-generated session index (zero-based)',
        )
        return parser


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
