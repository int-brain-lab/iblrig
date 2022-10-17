"""
Script used to test that pybpod launches with the given test data in the fixtures dir; ensure when running this script that the
iblrig_params dir already exists and that the script is executed from that dir (required for pybpod functionality)
"""
import argparse
import os
import shutil
from pathlib import Path
from sys import platform

# Set iblrig_params path based on platform
IBLRIG_PARAMS_PATH = Path("C:\\iblrig_params") if platform == "win32" else Path.home() / "Documents" / "iblrig_params"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup iblpybpod")
    parser.add_argument("-t", "--test", action="store_true", help="Removes local iblrig_params dir and copies test data")
    args = parser.parse_args()

    if args.test:
        for name in os.listdir(IBLRIG_PARAMS_PATH):  # delete the contents of the IBLRIG_PARAMS_PATH dir
            full_path = IBLRIG_PARAMS_PATH / str(name)
            shutil.rmtree(full_path) if Path(full_path).is_dir() else os.unlink(full_path)

        # Copies test data content to IBLRIG_PARAMS_PATH dir
        iblrig_path = Path(__file__).parents[1]
        shutil.copytree(iblrig_path / "test_iblrig" / "fixtures" / "test_iblrig_params", IBLRIG_PARAMS_PATH, dirs_exist_ok=True)

    # start pybpod
    from pybpodgui_plugin.__main__ import start as start_pybpod
    start_pybpod()
