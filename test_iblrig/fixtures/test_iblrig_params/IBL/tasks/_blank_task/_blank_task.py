import logging
from pathlib import Path
from iblrig.misc import call_exp_desc_gui
import json

log = logging.getLogger("iblrig")

ALYX_CONFIG_PATH = Path.home() / ".one" / ".alyx.internationalbrainlab.org"
with open(ALYX_CONFIG_PATH, "r") as f:
    data = json.load(f)
alyx_username = data["ALYX_LOGIN"]


call_exp_desc_gui(username = alyx_username)