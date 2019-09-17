#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, May 7th 2019, 12:07:26 pm
import json
import logging
import webbrowser as wb
from pathlib import Path

import ibllib.io.flags as flags
import ibllib.io.params as lib_params
import ibllib.io.raw_data_loaders as raw
import oneibl.params
from ibllib.pipes.experimental_data import create
from oneibl.one import ONE
import iblrig.params as rig_params

log = logging.getLogger('iblrig')


def get_one() -> type(ONE):
    try:
        one = ONE()
    except ConnectionError as e:
        log.error("Cannot create ONE object", e)
        one = None
    return one


def create_session(session_folder):
    pfile = Path(lib_params.getfile('lib_params'))
    if not pfile.exists():
        oneibl.params.setup_alyx_params()

    flags.create_create_flags(session_folder)
    create(session_folder, dry=False)


def open_session_narrative(session_url: str) -> None:
    wb.open_new_tab(session_url)


def load_previous_data(subject_nickname):
    one = get_one()
    eid = get_latest_session_eid(subject_nickname)
    return one.load(eid, dataset_types=['_iblrig_taskData.raw'])[0]


def load_previous_trial_data(subject_nickname):
    return load_previous_data(subject_nickname)[-1]


def load_previous_settings(subject_nickname):
    one = get_one()
    eid = get_latest_session_eid(subject_nickname)
    # det = one.alyx.rest('sessions', 'read', eid)
    # return json.loads(det['json'])
    return one.load(eid, dataset_types=['_iblrig_taskSettings.raw'])[0]


def get_latest_session_eid(subject_nickname):
    """Return the eID of the latest session for Subject that has data on
    Flatiron"""
    one = get_one()
    last_session = one.search(
        subject=subject_nickname,
        dataset_types=['_iblrig_taskData.raw', '_iblrig_taskSettings.raw'],
        limit=1)
    if last_session:
        return last_session[0]
    else:
        return None


def write_board_params(data: dict = None, force: bool = False) -> None:
    if data is None:
        data = rig_params.EMPTY_BOARD_PARAMS
        data['NAME'] = rig_params.get_board_name()
    board = data['NAME']
    one = get_one()
    p = load_board_params()
    if p and not force:
        log.info('Board params already present, exiting...')
        return p
    patch_dict = {
        "json": json.dumps(data)
    }
    one.alyx.rest('locations', 'partial_update', id=board, data=patch_dict)
    return data


def load_board_params() -> dict:
    board = rig_params.get_board_name()
    one = get_one()
    try:
        out = one.alyx.rest('locations', 'read', id=board)['json']
        out = json.loads(out)
    except Exception as e:
        log.error(e)
        out = None
    return out


def update_board_params(data: dict, force: bool = False) -> dict:
    old = load_board_params()
    if old is None:
        log.info("board params not found, creating...")
        write_board_params()
        old = load_board_params()

    board = rig_params.get_board_name()
    if data['NAME'] != board:
        log.error(f"Board {board} not equal to data['NAME'] {data['NAME']}")
        raise(AttributeError)
    for k in data:
        if k in old.keys():
            old[k] = data[k]
        else:
            if not force:
                log.info(f"Unknown key {k}: skipping key...")
                continue
            elif force:
                log.info(f"Adding new key {k} with value {data[k]} to {board} json field")
                old[k] = data[k]
    write_board_params(data=old, force=True)
    log.info(f'Changed board params: {data}')

    return old


def create_current_running_session(session_folder):
    one = get_one()
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
