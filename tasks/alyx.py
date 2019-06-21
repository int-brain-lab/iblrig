#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, May 7th 2019, 12:07:26 pm
import datetime
import json
import webbrowser as wb
from pathlib import Path

from dateutil import parser

import ibllib.io.flags as flags
import ibllib.io.params as params
import oneibl.params
from ibllib.pipes.experimental_data import create
from oneibl.one import ONE

one = ONE()


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
    """Return the eID of the latest session for Subject that has data on Flatiron"""
    last_session = one.search(
        subject=subject_nickname,
        dataset_types=['_iblrig_taskData.raw', '_iblrig_taskSettings.raw'],
        limit=1)
    if last_session:
        return last_session[0]
    else:
        return None


def init_board_params(board, reset=True):
    p = load_board_params(board)
    empty_params = {
        'WATER_CALIBRATION_RANGE': None,  # [min, max]
        'WATER_CALIBRATION_OPEN_TIMES': None,  # [float, float, ...]
        'WATER_CALIBRATION_WEIGHT_PERDROP': None,  # [float, float, ...]
        'SCREEN_CALIBRATION_FUNC': None,  # unknown
        'BPOD_COM': None,  # str
        'F2TTL_COM': None,  # str
        'ROTARY_ENCODER_COM': None,  # str
        'F2TTL_DARK_THRESH': None,  # float
        'F2TTL_LIGHT_THRESH': None  # float
    }
    if not reset:
        empty_params.update(p)
    patch_board_params(board, empty_params)
    return empty_params


def patch_board_params(board, param_dict):
    params = load_board_params(board)
    params.update(param_dict)
    patch_dict = {
        "json": json.dumps(params)
    }
    one.alyx.rest('locations', 'partial_update', id=board, data=patch_dict)
    return params


def load_board_params(board):
    return json.loads(one.alyx.rest('locations', 'read', id=board)['json'])


if __name__ == "__main__":
    subject = 'ZM_1737'
    session_folder = '/home/nico/Projects/IBL/scratch/test_iblrig_data/Subjects/_iblrig_test_mouse/2019-05-08/001'


    # eid = get_latest_session_eid(subject, has_data=True)
    data = load_previous_data(subject)
    last_trial_data = load_previous_trial_data(subject)
    settings = load_previous_settings(subject)

    create_session(session_folder)

    board = '_iblrig_mainenlab_behavior_0'
    init_board_params(board)
    patch_board_params(board, {'some_var': 123, 'BPOD_COM': 'COM#'})
    load_board_params(board)

    print('.')
