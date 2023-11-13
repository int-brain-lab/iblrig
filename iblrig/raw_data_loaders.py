import json
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger('iblrig')


# class definition with no init is used as a namespace
class jsonable:
    def read(file, offset=None):
        data = []
        with open(file) as f:
            if offset is not None:
                f.seek(offset, 0)
            for line in f:
                data.append(json.loads(line))
        return data

    def _write(file, data, mode):
        with open(file, mode) as f:
            for obj in data:
                f.write(json.dumps(obj) + '\n')

    def write(file, data):
        jsonable._write(file, data, 'w+')

    def append(file, data):
        jsonable._write(file, data, 'a')


def assert_valid_video_label(label):
    """
    Raises a value error is the provided label is not supported.
    :param label: A video label to verify
    :return: the label in lowercase
    """
    video_labels = ('left', 'right', 'body')
    if not isinstance(label, str):
        try:
            return tuple(map(assert_valid_video_label, label))
        except AttributeError as e:
            raise ValueError('label must be string or iterable of strings') from e
    if label.lower() not in video_labels:
        raise ValueError(f"camera must be one of ({', '.join(video_labels)})")
    return label.lower()


def load_task_jsonable(jsonable_file, offset=0):
    """
    Reads in a task data jsonable file and returns a trials dataframe and a bpod data list
    :param jsonable_file: a full-path to the jsonable file
    :return:
        trials_table: a pandas Dataframe with the trial info in the same format as the Session trials table
        bpod_data: a list [n_trials] for each of the
    """
    trials_table = jsonable.read(jsonable_file, offset=offset)
    # pop-out the bpod data from the table
    bpod_data = []
    for td in trials_table:
        bpod_data.append(td.pop('behavior_data'))

    trials_table = pd.DataFrame(trials_table)
    return trials_table, bpod_data


def load_settings(session_path: str | Path, collection='raw_behavior_data'):
    """
    Load PyBpod Settings files (.json).

    [description]

    :param session_path: Absolute path of session folder
    :type session_path: str, Path
    :return: Settings dictionary
    :rtype: dict
    """
    if session_path is None:
        log.warning('No data loaded: session_path is None')
        return
    path = Path(session_path).joinpath(collection)
    path = next(path.glob('_iblrig_taskSettings.raw*.json'), None)
    if not path:
        log.warning('No data loaded: could not find raw settings file')
        return None
    with open(path) as f:
        settings = json.load(f)
    if 'IBLRIG_VERSION_TAG' not in settings.keys():
        settings['IBLRIG_VERSION_TAG'] = ''
    return settings


def get_port_events(trial: dict, name: str = '') -> list:
    """get_port_events
    Return all event timestamps from bpod raw data trial that match 'name'
    --> looks in trial['behavior_data']['Events timestamps']

    :param trial: raw trial dict
    :type trial: dict
    :param name: name of event, defaults to ''
    :type name: str, optional
    :return: Sorted list of event timestamps
    :rtype: list
    TODO: add polarities?
    """
    out: list = []
    events = trial['behavior_data']['Events timestamps']
    for k in events:
        if name in k:
            out.extend(events[k])
    out = sorted(out)

    return out
