"""
Removes pybpod data files from setup folders.
Data and settings from pybpod data files is in ibl data files.
Assumes it's called as a post command from task folder
"""
from pathlib import Path
import os


IBLRIG_FOLDER = Path(__file__).absolute().parent.parent
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"

experiments_folder = IBLRIG_PARAMS_FOLDER / "IBL" / "experiments"

sess_folders = experiments_folder.rglob("sessions")

for s in sess_folders:
    if "setups" in str(s):
        os.system(f"rd /s /q {str(s)}")
