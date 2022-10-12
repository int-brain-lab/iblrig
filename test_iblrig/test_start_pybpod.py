"""
Script used to test that pybpod launches with the given test data in the fixtures dir; ensure when running this script that the
iblrig_params dir already exists and that the script is executed from that dir
"""
import argparse
import os
import shutil
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup iblpybpod")
    parser.add_argument("-t", "--test", action="store_true", help="Test mode")
    args = parser.parse_args()

    if args.test:  # Set vars for testing mode and copy files to appropriate dirs
        iblrig_path = Path(__file__).parents[1]
        iblrig_params_path = Path.home() / "Documents" / "iblrig_params"
        shutil.copytree(iblrig_path / "test_iblrig" / "fixtures" / "test_iblrig_params", iblrig_params_path, dirs_exist_ok=True)
    else:
        iblrig_path = Path("C:\\iblrig")
        iblrig_params_path = Path("C:\\iblrig_params")
        os.makedirs(iblrig_params_path, exist_ok=True)  # Create params dir if it does not already exist

        # Copy test pybpod user_settings.py from iblrig repo to params dir
        src_file = iblrig_path / "scripts" / "user_settings.py"
        dst_file = iblrig_params_path / "user_settings.py"
        shutil.copy(src_file, dst_file) if not dst_file.exists() else None

    # start pybpod
    from pybpodgui_plugin.__main__ import start as start_pybpod
    start_pybpod()
