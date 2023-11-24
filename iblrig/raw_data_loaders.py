import json
from typing import Any

import pandas as pd

from iblutil.util import setup_logger

log = setup_logger('iblrig')


def load_task_jsonable(jsonable_file: str, offset: int | None = None) -> tuple[pd.DataFrame, list[Any]]:
    """
    Reads in a task data jsonable file and returns a trials dataframe and a bpod data list.

    Parameters:
    - jsonable_file (str): full path to jsonable file.
    - offset (int or None): The offset to start reading from (default: None).

    Returns:
    - tuple: A tuple containing:
        - trials_table (pandas.DataFrame): A DataFrame with the trial info in the same format as the Session trials table.
        - bpod_data (list): timing data for each trial
    """
    trials_table = []
    with open(jsonable_file) as f:
        if offset is not None:
            f.seek(offset, 0)
        for line in f:
            trials_table.append(json.loads(line))

    # pop-out the bpod data from the table
    bpod_data = []
    for td in trials_table:
        bpod_data.append(td.pop('behavior_data'))

    trials_table = pd.DataFrame(trials_table)
    return trials_table, bpod_data
