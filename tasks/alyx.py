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
    eid = get_latest_session_eid(subject_nickname, has_data=True)

    return one.load(eid, dataset_types=['_iblrig_taskData.raw'])


def load_previous_settings(subject_nickname):
    eid = get_latest_session_eid(subject_nickname, has_data=True)
    det = one.alyx.rest('sessions', 'read', eid)

    return json.loads(det['json'])


def get_latest_session_eid(subject_nickname, has_data=True, details=False):
    date = datetime.datetime.now().date().isoformat()

    if has_data:
        eid = one.search(
            subject=subject_nickname,
            dataset_types=['_iblrig_taskData.raw', '_iblrig_taskSettings.raw'],
            date_range=['1970-1-1', date]
        )[-1]
    else:
        eid = one.search(subject=subject, date_range=['1970-1-1', date])[-1]

    det = one.alyx.rest('sessions', 'read', eid)
    return (eid, det) if details else eid


if __name__ == "__main__":
    subject = 'ZM_1085'
    session_folder = '/home/nico/Projects/IBL/scratch/test_iblrig_data/Subjects/_iblrig_test_mouse/2019-05-08/001'


    eid, det = get_latest_session_eid(subject, has_data=True, details=True)
    data = load_previous_data(subject)
    settings = load_previous_settings(subject)

    create_session(session_folder)


    print('.')
