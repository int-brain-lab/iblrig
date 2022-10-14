import subprocess
from pathlib import Path

import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler
from iblrig.path_helper import get_bonsai_path

# r = "/home/nico/Projects/IBL/github/iblrig"
# task_settings.IBLRIG_FOLDER = r
# d = ("/home/nico/Projects/IBL/github/iblrig/scratch/" +
#      "test_iblrig_data")
# task_settings.IBLRIG_DATA_FOLDER = d


sph = SessionParamHandler(task_settings, user_settings)

server = Path(sph.IBLRIG_FOLDER) / "visual_stim" / "screen_calibration" / "photodiode_server.py"
# Start the frame2TTL server
# server_cmd = ['python', server, sph.PARAMS['COM_F2TTL']]
# server = subprocess.Popen(server_cmd, stdout=subprocess.PIPE)
# print(server)

bns = get_bonsai_path()
# Path(sph.IBLRIG_FOLDER) / "Bonsai" / "Bonsai64.exe"
# if not bns.exists():
#     bns = Path(sph.IBLRIG_FOLDER) / "Bonsai" / "Bonsai.exe"
wrkfl = Path(sph.IBLRIG_FOLDER) / "visual_stim" / "screen_calibration" / "screen_sweep.bonsai"
noedit = "--no-editor"  # implies start
nodebug = "--start-no-debug"
start = "--start"
editor = nodebug
# Properties
save = "-p:Save=True"
fname = "-p:FileName={sph}_iblrig_calibration_screen_brightness.raw.ssv"
rgb = "-p:RGB=RGB"

cmd = [bns, wrkfl, editor, save, fname, rgb]
s = subprocess.call(cmd, stdout=subprocess.PIPE)
print("bla")
t = subprocess.run(["ls", "s"], stdout=subprocess.PIPE)
print(s)
print(t)
print(".")
