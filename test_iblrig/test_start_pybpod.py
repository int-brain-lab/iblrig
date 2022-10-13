"""
Script used to test that pybpod launches with the given test data in the fixtures dir; ensure when running this script that the
iblrig_params dir already exists and that the script is executed from that dir (required for pybpod functionality)
"""
import argparse
import shutil
from pathlib import Path
from sys import platform

# Set iblrig_params path based on platform
IBLRIG_PARAMS_PATH = Path("C:\\iblrig_params") if platform == "win32" else Path.home() / "Documents" / "iblrig_params"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup iblpybpod")
    parser.add_argument("-t", "--test", action="store_true", help="Removes local iblrig_params dir and copies test data")
    args = parser.parse_args()

    iblrig_path = Path(__file__).parents[1]
    if args.test:  # Set vars for testing mode and copy files to appropriate dirs
        shutil.rmtree(IBLRIG_PARAMS_PATH)
        shutil.copytree(iblrig_path / "test_iblrig" / "fixtures" / "test_iblrig_params", IBLRIG_PARAMS_PATH, dirs_exist_ok=True)

    # start pybpod
    from pybpodgui_plugin.__main__ import start as start_pybpod
    start_pybpod()
