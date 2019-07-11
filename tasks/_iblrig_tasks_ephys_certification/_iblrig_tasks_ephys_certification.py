import subprocess
from pathlib import Path

import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler

sph = SessionParamHandler(task_settings, user_settings)

bns = Path(sph.IBLRIG_FOLDER) / 'Bonsai' / 'Bonsai64.exe'
wrkfl = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / \
    'ephys_certification' / 'certification.bonsai'
# Flags
noedit = '--no-editor'  # implies start and no-debug?
nodebug = '--start-no-debug'
start = '--start'
editor = start
# Properties
save = '-p:Save=True'
fname = '-p:FileName=some_file_name.ext'

cmd = [bns, wrkfl, editor, save, fname]
s = subprocess.call(cmd, stdout=subprocess.PIPE)
print('bla')
t = subprocess.run(['ls', 's'], stdout=subprocess.PIPE)
print(s)
print(t)
print('.')
