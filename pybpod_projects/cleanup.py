"""
Removes pybpod data files from setup folders.
Data and settings from pybpod data files is in ibl data files.
Assumes it's called as a post command from task folder
"""
from pathlib import Path
import shutil

p = Path.cwd()
print('\n', p, '\n')
print('\n', p.parent.parent.parent, '\n')

sess_folders = p.parent.parent.parent.rglob('sessions')
print('\n', sess_folders, '\n')

for s in sess_folders:
    print('\n', s, '\n')
    if 'setups' in str(s):
        shutil.rmtree(s)
