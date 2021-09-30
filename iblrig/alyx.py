#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: iblrig/alyx.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Tuesday, May 7th 2019, 12:07:26 pm
import json
import logging
import webbrowser as wb

import ibllib.io.raw_data_loaders as raw
from ibllib.oneibl.registration import RegistrationClient

from one.api import ONE

import iblrig.params as rig_params

log = logging.getLogger("iblrig")


def check_alyx_ok():
    try:
        ONE()
        return True
    except Exception as e:
        print(e)
        log.warning("Cannot create one client: working offline")
        return False


def create_session(session_folder, one=None):
    one = one or ONE()

    RegistrationClient(one=one).register_session(session_folder, file_list=False)


def open_session_narrative(session_url: str) -> None:
    wb.open_new_tab(session_url)


def load_previous_data(subject_nickname, one=None):
    one = one or ONE()
    eid = get_latest_session_eid(subject_nickname)
    return one.load(eid, dataset_types=["_iblrig_taskData.raw"])[0]


def load_previous_trial_data(subject_nickname, one=None):
    one = one or ONE()
    return load_previous_data(subject_nickname, one=one)[-1]


def load_previous_settings(subject_nickname, one=None):
    one = one or ONE()
    eid = get_latest_session_eid(subject_nickname, one=one)
    # det = one.alyx.rest('sessions', 'read', eid)
    # return json.loads(det['json'])
    return one.load(eid, dataset_types=["_iblrig_taskSettings.raw"])[0]


def get_latest_session_eid(subject_nickname, one=None):
    """Return the eID of the latest session for Subject that has data on
    Flatiron"""
    one = one or ONE()
    last_session = one.search(
        subject=subject_nickname,
        dataset_types=["_iblrig_taskData.raw", "_iblrig_taskSettings.raw"],
        limit=1,
    )
    if last_session:
        return last_session[0]
    else:
        return None


def write_alyx_params(data: dict, force: bool = False, one=None) -> None:
    one = one or ONE()
    p = load_alyx_params(data["NAME"], one=one)
    if p and not force:
        log.info("Board params already present, exiting...")
        return p
    board = data["NAME"]
    patch_dict = {"json": data}
    one.alyx.rest("locations", "partial_update", id=board, data=patch_dict)
    return data


def load_alyx_params(board: str, one=None) -> dict:
    one = one or ONE()
    try:
        out = one.alyx.rest("locations", "read", id=board)["json"]
        if isinstance(out, str):
            out = json.loads(out)
    except Exception as e:
        log.error(e)
        out = None
    return out


def update_alyx_params(data: dict, force: bool = False, one=None) -> dict:
    """Updates keys in data dict to json field in alyx
    If keys don't exist already will skip them
    """
    one = one or ONE()
    board = rig_params.get_board_name()
    if "NAME" in data and data["NAME"] != board:
        log.error(f"Board {board} not equal to data['NAME'] {data['NAME']}")
        raise (AttributeError)
    old = load_alyx_params(board, one=one)
    if old is None:
        log.info("board params not found, creating...")
        new = rig_params.create_new_params_dict()
        write_alyx_params(new, one=one)
        old = load_alyx_params(new["NAME"], one=one)

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
    write_alyx_params(data=old, force=True, one=one)
    log.info(f"Changed board params: {data}")

    return old


def create_current_running_session(session_folder, one=None):
    one = one or ONE()
    settings = raw.load_settings(session_folder)
    subject = one.alyx.rest("subjects?nickname=" + settings["PYBPOD_SUBJECTS"][0], "list")[0]
    ses_ = {
        "subject": subject["nickname"],
        "users": [settings["PYBPOD_CREATOR"][0]],
        "location": settings["PYBPOD_BOARD"],
        "procedures": ["Behavior training/tasks"],
        "lab": subject["lab"],
        "type": "Experiment",
        "task_protocol": settings["PYBPOD_PROTOCOL"] + settings["IBLRIG_VERSION_TAG"],
        "number": settings["SESSION_NUMBER"],
        "start_time": settings["SESSION_DATETIME"],
        "end_time": None,
        "n_correct_trials": None,
        "n_trials": None,
        "json": None,
    }
    session = one.alyx.rest("sessions", "create", data=ses_)
    return session


def update_completed_session(session_folder):
    pass


# # Methods for tasks from alyx w/ fallback
# def update_params(data: dict) -> None:
#     rig_params.update_params_file(data=data)
#     try:
#         update_alyx_params(data=data)
#     except Exception as e:
#         log.warning(
#             f"Could not update board params on Alyx. Saved locally:\n{data}\n{e}"
#         )


# def load_params() -> dict:
#     params_local = rig_params.load_params_file()
#     params_alyx = load_alyx_params(params_local["NAME"])
#     if params_alyx is None:
#         log.warning(f"Could not load board params from Alyx.")
#     if params_alyx != params_local:
#         log.warning(f"Local data and Alyx data mismatch. Trying to update Alyx.")
#         update_alyx_params(data=params_local, force=True)
#     return params_local


# def write_params(data: dict = None, force: bool = False, upload: bool = True) -> None:
#     rig_params.write_params_file(data=data, force=force)
#     if upload:
#         try:
#             write_alyx_params(data=data, force=force)
#         except Exception as e:
#             log.warning(
#                 f"Could not write board params to Alyx. Written to local file:\n{e}"
#             )
#     return


def sync_alyx_subjects(one=None):
    one = one or ONE()


if __name__ == "__main__":
    # subject = 'ZM_1737'

    # session_folder = '/home/nico/Projects/IBL/github/iblrig_data/\
    #     Subjects/_iblrig_test_mouse/2019-06-24/001'.replace(' ', '')

    # eid = get_latest_session_eid(subject, has_data=True)
    # data = load_previous_data(subject)
    # last_trial_data = load_previous_trial_data(subject)
    # settings = load_previous_settings(subject)

    # create_session(session_folder)

    data = {
        "COM_F2TTL": "COM6",
        "F2TTL_DARK_THRESH": 86.0,
        "F2TTL_LIGHT_THRESH": 46.0,
        "F2TTL_CALIBRATION_DATE": "2019-09-26",
    }
    # init_board_params(board)
    update_alyx_params(data)
    # load_alyx_params(board)

    # create_current_running_session(session_folder)
    # create_session(session_folder)

    print(".")
