import json
import logging

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
