#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, May 7th 2019, 12:07:26 pm
import json
import webbrowser as wb
from pathlib import Path

import ibllib.io.flags as flags
import ibllib.io.params as params
import ibllib.io.raw_data_loaders as raw
import oneibl.params
from ibllib.pipes.experimental_data import create
from oneibl.one import ONE

one = ONE()
EMPTY_BOARD_PARAMS = {
    'WATER_CALIBRATION_RANGE': None,  # [min, max]
    'WATER_CALIBRATION_OPEN_TIMES': None,  # [float, float, ...]
    'WATER_CALIBRATION_WEIGHT_PERDROP': None,  # [float, float, ...]
    'BPOD_COM': None,  # str
    'F2TTL_COM': None,  # str
    'ROTARY_ENCODER_COM': None,  # str
    'F2TTL_DARK_THRESH': None,  # float
    'F2TTL_LIGHT_THRESH': None  # float
}


def create_session(session_folder):
    pfile = Path(params.getfile('one_params'))
    if not pfile.exists():
        oneibl.params.setup_alyx_params()

    flags.create_create_flags(session_folder)
    create(session_folder, dry=False)


def open_session_narrative(session_url: str) -> None:
    wb.open_new_tab(session_url)


def load_previous_data(subject_nickname):
    eid = get_latest_session_eid(subject_nickname)
    return one.load(eid, dataset_types=['_iblrig_taskData.raw'])[0]


def load_previous_trial_data(subject_nickname):
    return load_previous_data(subject_nickname)[-1]


def load_previous_settings(subject_nickname):
    eid = get_latest_session_eid(subject_nickname)
    # det = one.alyx.rest('sessions', 'read', eid)
    # return json.loads(det['json'])
    return one.load(eid, dataset_types=['_iblrig_taskSettings.raw'])[0]


def get_latest_session_eid(subject_nickname):
    """Return the eID of the latest session for Subject that has data on
    Flatiron"""
    last_session = one.search(
        subject=subject_nickname,
        dataset_types=['_iblrig_taskData.raw', '_iblrig_taskSettings.raw'],
        limit=1)
    if last_session:
        return last_session[0]
    else:
        return None


def init_board_params(board, force=False):
    p = load_board_params(board)
    if p and not force:
        print('Board params already present, exiting...')
        return p
    empty_params = EMPTY_BOARD_PARAMS
    patch_dict = {
        "json": json.dumps(empty_params)
    }
    one.alyx.rest('locations', 'partial_update', id=board, data=patch_dict)
    return empty_params


def change_board_params(board, **kwargs):
    if not all(kwargs.keys() in EMPTY_BOARD_PARAMS):
        print('Not all keys exist in board params')
        return
    else:
        update_board_params(board, kwargs)
        print(f'Changed board params: {kwargs}')


def update_board_params(board, param_dict):
    params = load_board_params(board)
    params.update(param_dict)
    patch_dict = {
        "json": json.dumps(params)
    }
    one.alyx.rest('locations', 'partial_update', id=board, data=patch_dict)
    return params


def load_board_params(board):
    json_field = one.alyx.rest('locations', 'read', id=board)['json']
    if json_field is not None:
        json_field = json.loads(json_field)
    else:
        json_field = {}
    return json_field


def create_current_running_session(session_folder):
    settings = raw.load_settings(session_folder)
    subject = one.alyx.rest(
        'subjects?nickname=' + settings['PYBPOD_SUBJECTS'][0], 'list')[0]
    ses_ = {'subject': subject['nickname'],
            'users': [settings['PYBPOD_CREATOR'][0]],
            'location': settings['PYBPOD_BOARD'],
            'procedures': ['Behavior training/tasks'],
            'lab': subject['lab'],
            'type': 'Experiment',
            'task_protocol':
                settings['PYBPOD_PROTOCOL'] + settings['IBLRIG_VERSION_TAG'],
            'number': settings['SESSION_NUMBER'],
            'start_time': settings['SESSION_DATETIME'],
            'end_time': None,
            'n_correct_trials': None,
            'n_trials': None,
            'json': None,
            }
    session = one.alyx.rest('sessions', 'create', data=ses_)
    return session


def update_completed_session(session_folder):
    pass


if __name__ == "__main__":
    subject = 'ZM_1737'

    session_folder = '/home/nico/Projects/IBL/github/iblrig_data/\
        Subjects/_iblrig_test_mouse/2019-06-24/001'.replace(' ', '')

    # eid = get_latest_session_eid(subject, has_data=True)
    data = load_previous_data(subject)
    last_trial_data = load_previous_trial_data(subject)
    settings = load_previous_settings(subject)

    # create_session(session_folder)

    board = '_iblrig_mainenlab_behavior_0'
    # init_board_params(board)
    # update_board_params(board, {'some_var': 123, 'BPOD_COM': 'COM#'})
    # load_board_params(board)

    create_current_running_session(session_folder)
    create_session(session_folder)

    print('.')
