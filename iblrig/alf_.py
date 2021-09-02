#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, May 7th 2019, 12:07:26 pm
import datetime
import json
import logging
# import webbrowser as wb
from pathlib import Path, PurePath

# import ibllib.io.flags as flags
# import ibllib.io.params as lib_params
# import ibllib.io.raw_data_loaders as raw
import oneibl.params  # XXX: Check THIS!
# from ibllib.pipes.experimental_data import create
from one.api import ONE

# import iblrig.params as rig_params

log = logging.getLogger("iblrig")


def which_tables(alf_dir=None):
    alf_dir = alf_dir or get_alf_dir_from_one_params()
    alf_dir = Path(alf_dir)
    meta_files = list(alf_dir.rglob("*.metadata.*"))  # noqa
    # XXX: FINISH ME


def sync_alyx(one=None):
    one = one or ONE()
    alf_dir = get_alf_dir_from_one_params()  # noqa
    sync_alyx_table('subjects', one=one)
    sync_alyx_table('subjects', one=one)

# Get root data folder from ONE params
def get_alf_dir_from_one_params() -> str:
    one_params = oneibl.params.get().as_dict()  # XXX: Check THIS!
    data_dir = one_params['CACHE_DIR']
    alf_dir = Path(data_dir).joinpath('.alf')
    if not alf_dir.exists():
        alf_dir.mkdir()
    return str(alf_dir)


def get_alf_dir_from_one(one: ONE = None) -> str:
    one = one or ONE()
    try:
        data_dir = one.alyx.cache_dir
    except BaseException:
        data_dir = one._par.as_dict()['CACHE_DIR']
    alf_dir = Path(data_dir).joinpath('.alf')
    if not alf_dir.exists():
        alf_dir.mkdir()
    return str(alf_dir)


# Create/Sync .alf/subjects.metadata.json
one = ONE(base_url='https://alyx.internationalbrainlab.org')
# Create/Sync .alf/lab_locations.metadata.json
# Create/Sync .alf/users.metadata.json

# Read local, check dump_date, compare to threshold, return OR try sync then Read local

def sync_alyx_table(table_name, one=None, save=True):
    one = one or ONE()
    alf_dir = Path(get_alf_dir_from_one(one=one))
    sync_status = None  # noqa
    if table_name == 'subjects':
        table = one.alyx.rest(table_name, 'list')
        table.append({'dump_date': datetime.datetime.utcnow().isoformat()})
        with open(alf_dir / f'{table_name}.metadata.json', 'a+') as f:
            json.dump(table, f, indent=1)


def check_sync_status(table_name, one=None):
    one = one or ONE()
    alf_dir = Path(get_alf_dir_from_one(one=one))  # noqa


ALF_PARAMS = {
    "default_root_data_dir": str(PurePath(Path.home(), "Downloads", "FlatIron")),
    "sync_frequency": 1  # Days
}


if __name__ == "__main__":
    pass
