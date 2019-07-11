"""
Removes pybpod data files from setup folders.
Data and settings from pybpod data files is in ibl data files.
Assumes it's called as a post command from task folder
"""
from pathlib import Path
import os

p = Path.cwd()

sess_folders = p.parent.parent.parent.rglob('sessions')

for s in sess_folders:
    if 'setups' in str(s):
        os.system(f"rd /s /q {str(s)}")
