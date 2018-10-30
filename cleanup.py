"""
Removes pybpod data files from setup folders.
Data and settings from pybpod data files is in ibl data files.
"""
from pathlib import Path
import shutil

p = Path.cwd()

sess_folders = p.rglob('sessions')

for s in sess_folders:
    if 'setups' in str(s):
        shutil.rmtree(s)
