import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.core.dtypes.concat import union_categoricals

log = logging.getLogger(__name__)
RE_PATTERN_EVENT = re.compile(r'^(\D+\d)_?(.+)$')


def load_task_jsonable(jsonable_file: str | Path, offset: int | None = None) -> tuple[pd.DataFrame, list[Any]]:
    """
    Reads in a task data jsonable file and returns a trials dataframe and a bpod data list.

    Parameters
    ----------
    - jsonable_file (str): full path to jsonable file.
    - offset (int or None): The offset to start reading from (default: None).

    Returns
    -------
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


def bpod_session_data_to_dataframe(bpod_data: list[dict[str, Any]], existing_data: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Convert Bpod session data into a single Pandas DataFrame.

    Parameters
    ----------
    bpod_data : list of dict
        A list of dictionaries as returned by load_task_jsonable, where each dictionary contains data for a single trial.
    existing_data : pd.DataFrame
        Existing dataframe that the incoming data will be appended to.

    Returns
    -------
    pd.DataFrame
        A Pandas DataFrame containing event data from the specified trials, with the following columns:

        *  Time : datetime.timedelta
              timestamp of the event (datetime.timedelta)
        *  Type : str (categorical)
              type of the event (TrialStart, StateStart, InputEvent, etc.)
        *  Trial : int
              index of the trial, zero-based
        *  State : str (categorical)
              name of the state
        *  Event : str (categorical)
              name of the event (only for type InputEvent)
        *  Channel : str (categorical)
              name of the event's channel (only for a subset of InputEvents)
        *  Value : int
              value of the event (only for a subset of InputEvents)
    """
    # define trial index
    trials = np.arange(len(bpod_data))
    if existing_data is not None and 'Trial' in existing_data:
        trials += existing_data.iloc[-1].Trial + 1

    # loop over requested trials
    dataframes = [] if existing_data is None or len(existing_data) == 0 else [existing_data]
    for index, trial in enumerate(trials):
        dataframes.append(bpod_trial_data_to_dataframe(bpod_data[index], trial))

    # combine trials into a single dataframe
    categories_type = union_categoricals([df['Type'] for df in dataframes])
    categories_state = union_categoricals([df['State'] for df in dataframes])
    categories_event = union_categoricals([df['Event'] for df in dataframes])
    categories_channel = union_categoricals([df['Channel'] for df in dataframes])
    for df in dataframes:
        df['Type'] = df['Type'].cat.set_categories(categories_type.categories)
        df['State'] = df['State'].cat.set_categories(categories_state.categories)
        df['Event'] = df['Event'].cat.set_categories(categories_event.categories)
        df['Channel'] = df['Channel'].cat.set_categories(categories_channel.categories)
    return pd.concat(dataframes)


def bpod_trial_data_to_dataframe(bpod_trial_data: dict[str, Any], trial: int) -> pd.DataFrame:
    """
    Convert a single Bpod trial's data into a Pandas DataFrame.

    Parameters
    ----------
    bpod_trial_data : dict
        A dictionary containing data for a single trial, including timestamps and events.
    trial : int
        An integer representing the trial index.

    Returns
    -------
    pd.DataFrame
        A Pandas DataFrame containing event data from the specified trial, with the following columns:

        *  Time : datetime.timedelta
              timestamp of the event (datetime.timedelta)
        *  Type : str (categorical)
              type of the event (TrialStart, StateStart, InputEvent, etc.)
        *  Trial : int
              index of the trial, zero-based
        *  State : str (categorical)
              name of the state
        *  Event : str (categorical)
              name of the event (only for type InputEvent)
        *  Channel : str (categorical)
              name of the event's channel (only for a subset of InputEvents)
        *  Value : int
              value of the event (only for a subset of InputEvents)
    """
    trial_start = bpod_trial_data['Trial start timestamp']
    trial_end = bpod_trial_data['Trial end timestamp']

    state_times = bpod_trial_data['States timestamps'].items()
    event_times = bpod_trial_data['Events timestamps'].items()

    # convert bpod data to list of tuples
    event_list = [(0, 'TrialStart', pd.NA, pd.NA)]
    event_list += [(t, 'StateStart', state, pd.NA) for state, times in state_times for t, _ in times if not np.isnan(t)]
    event_list += [(t, 'InputEvent', pd.NA, event) for event, times in event_times for t in times]
    event_list += [(t, 'StateEnd', state, pd.NA) for state, times in state_times for _, t in times if not np.isnan(t)]
    event_list += [(trial_end - trial_start, 'TrialEnd', pd.NA, pd.NA)]
    event_list = sorted(event_list)

    # create dataframe with TimedeltaIndex
    df = pd.DataFrame(data=event_list, columns=['Time', 'Type', 'State', 'Event'])
    df.Time = pd.to_timedelta(df.Time + trial_start, unit='seconds')
    df.set_index('Time', inplace=True)
    df.rename_axis(index=None, inplace=True)

    # cast types
    df['Type'] = df['Type'].astype('category')
    df['State'] = df['State'].astype('category').ffill()
    df['Event'] = df['Event'].astype('category')
    df.insert(2, 'Trial', pd.to_numeric(pd.Series(trial, index=df.index), downcast='unsigned'))

    # deduce channels and values from event names
    df[['Channel', 'Value']] = df['Event'].str.extract(RE_PATTERN_EVENT, expand=True)
    df['Channel'] = df['Channel'].astype('category')
    df['Value'] = df['Value'].replace({'Low': 0, 'High': 1, 'Out': 0, 'In': 1})
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce', downcast='unsigned', dtype_backend='numpy_nullable')

    return df
