import logging
import os
from pathlib import Path
from iblrig.misc import call_exp_desc_gui

import json

log = logging.getLogger("iblrig")

ALYX_CONFIG_PATH = Path.home() / ".one" / ".alyx.internationalbrainlab.org"
with open(ALYX_CONFIG_PATH, "r") as f:
    data = json.load(f)
alyx_username = data["ALYX_LOGIN"]

subject_name = None
if "user_settings.py" in os.listdir():
    with open("user_settings.py", "r") as f:
        lines = f.readlines()
    for row in lines:
        if "PYBPOD_SUBJECT_EXTRA" in row:
            pybpod_subject_extra = row
            name_index = row.split().index('"name":')
            subject_name = row.split()[name_index+1].strip(",\"")
            break

if alyx_username and subject_name:
    call_exp_desc_gui(username = alyx_username, subject = subject_name)
