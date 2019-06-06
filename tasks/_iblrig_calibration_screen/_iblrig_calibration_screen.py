import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler
import subprocess
from pathlib import Path

r = "/home/nico/Projects/IBL/github/iblrig"
task_settings.IBLRIG_FOLDER = r
d = ("/home/nico/Projects/IBL/github/iblrig/scratch/" +
     "test_iblrig_data")
task_settings.IBLRIG_DATA_FOLDER = d


sph = SessionParamHandler(task_settings, user_settings)

server = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / \
    'screen_calibration' / 'photodiode_server.py'

# Start the frame2TTL server
# server_cmd = ['python', server, sph.COM['FRAME2TTL']]
# server = subprocess.Popen(server_cmd, stdout=subprocess.PIPE)
# print(server)
cmd = ['ls', '..']
s = subprocess.run(cmd, stdout=subprocess.PIPE)
print('bla')
t = subprocess.run(['ls','s'], stdout=subprocess.PIPE)
print(s)
print(t)
print('.')
