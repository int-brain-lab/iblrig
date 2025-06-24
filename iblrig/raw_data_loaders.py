import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.core.dtypes.concat import union_categoricals

log = logging.getLogger(__name__)
RE_PATTERN_EVENT = re.compile(r'^(?P<Channel>\D+\d?)_?(?P<Value>.*)$')


def load_task_jsonable(jsonable_file: str | Path, offset: int = 0) -> tuple[pd.DataFrame, list[Any]]:
    """
    Reads in a task data jsonable file and returns a trials dataframe and a bpod data list.

    Parameters
    ----------
    jsonable_file : str or Path
        full path to jsonable file.
    offset : int, optional
        The offset to start reading from. Defaults to 0.

    Returns
    -------
    tuple
        A tuple containing

        *  trials_table : pandas.DataFrame
              A DataFrame with the trial info in the same format as the Session trials table.
        *  bpod_data : list
              timing data for each trial
    """
    with open(jsonable_file) as f:
        f.seek(offset, 0)
        trials_table = [json.loads(line) for line in f]

    # pop out bpod data
    bpod_data = [td.pop('behavior_data') for td in trials_table]

    return pd.DataFrame(trials_table), bpod_data


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

    return concat_bpod_dataframes(dataframes)


def concat_bpod_dataframes(dataframes: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Concatenate a list of DataFrames containing Bpod trial data into a single DataFrame.

    Parameters
    ----------
    dataframes : list of DataFrames
        A list of dictionaries as returned by load_task_jsonable, where each dictionary contains data for a single trial.

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


def bpod_trial_data_to_dataframes(
    bpod_trial_data: list[dict[str, Any]], existing_data: list[pd.DataFrame] | None = None
) -> list[pd.DataFrame]:
    """
    Convert a list of Bpod trial data dictionaries into a list of Pandas DataFrames.

    Each DataFrame corresponds to a single trial's data, as returned by `bpod_trial_data_to_dataframe`. If existing DataFrames are
    provided, the new DataFrames will be appended to this list.

    Parameters
    ----------
    bpod_trial_data : list of dict
        A list of dictionaries, where each dictionary contains data for a single trial.
    existing_data : list of pd.DataFrame, optional
        An optional list of existing DataFrames to which the new DataFrames will be appended. If None, a new list will be created.

    Returns
    -------
    list of pd.DataFrame
        A list of Pandas DataFrames, each containing event data from the corresponding trial.
    """
    dataframes = existing_data if existing_data is not None else list()
    trial_number = len(dataframes)
    for single_trial_data in bpod_trial_data:
        dataframes.append(bpod_trial_data_to_dataframe(bpod_trial_data=single_trial_data, trial=trial_number))
        trial_number += 1
    return dataframes


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
    df.Time = np.array((df.Time + trial_start) * 1e6, dtype='timedelta64[us]')
    df.set_index('Time', inplace=True)

    # cast types
    df['Type'] = df['Type'].astype('category')
    df['State'] = df['State'].astype('category').ffill()
    df['Event'] = df['Event'].astype('category')
    df.insert(2, 'Trial', pd.to_numeric([trial], downcast='unsigned')[0])

    # extract channel name and value from Event strings
    # since 'Event' is categorical, only process its unique values for performance
    mappings = df['Event'].cat.categories.to_series().str.extract(RE_PATTERN_EVENT, expand=True)
    mappings['Channel'] = mappings['Channel'].astype('category')
    mappings['Value'] = mappings['Value'].replace({'Low': '0', 'High': '1', 'Out': '0', 'In': '1'})
    mappings['Value'] = pd.to_numeric(mappings['Value'], errors='coerce', downcast='unsigned', dtype_backend='numpy_nullable')

    # map the extracted channel and value information back to the DataFrame.
    df['Channel'] = df['Event'].map(mappings['Channel'])
    df['Value'] = df['Event'].map(mappings['Value'])

    return df
