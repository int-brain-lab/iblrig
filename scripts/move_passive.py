#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, December 2nd 2019, 4:52:40 pm
import shutil
from pathlib import Path

import ibllib.io.raw_data_loaders as raw
import ibllib.pipes.misc as misc
import iblrig.path_helper as ph

IBLRIG_DATA_PATH = Path(ph.get_iblrig_data_folder())

ephys_sessions = IBLRIG_DATA_PATH.rglob("raw_passive_data_missing.flag")
passive_sessions = IBLRIG_DATA_PATH.rglob("passive_data_for_ephys.flag")

# For each passive session found look into passiveSettings to find ephysSession name
# search for the ephys session session in the rglobbed ephys sessions
# If you find it just rename and move the folder raw_behavior_data -> raw_passive_data,
# If no find search specifically for that session from the metadata and try to copy the folder
# If folder exists throw an error
for ps in passive_sessions:
    sett = raw.load_settings(str(ps.parent))
    esess = sett['CORRESPONDING_EPHYS_SESSION']
    # Fails if dst_folder exists!
    misc.transfer_folder(
        str(ps.parent / 'raw_behavior_data'),
        str(Path(esess) / 'raw_passive_data'),
        force=False
    )
