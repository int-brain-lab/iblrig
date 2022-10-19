"""
Script used to test that pybpod launches with the given test data in the pybpod_fixtures dir; ensure when running this script
that the iblrig_params dir already exists and that the script is executed from within that dir (required for pybpod functionality)
Script is not intended to be run in the CI.
"""
import argparse
import os
import shutil
from pathlib import Path

import iblrig.path_helper as path_helper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Start pybpod")
    parser.add_argument("-t", "--test", action="store_true", help="Removes local iblrig_params dir and copies test data")
    args = parser.parse_args()

    if args.test:
        for name in os.listdir(path_helper.get_iblrig_params_folder()):  # delete the contents of the ibl_params dir (pybpod dir)
            full_path = Path(path_helper.get_iblrig_params_folder()) / name
            shutil.rmtree(full_path) if Path(full_path).is_dir() else os.unlink(full_path)

        # Copy pybpod_fixtures content to ibl_params dir (pybpod dir)
        shutil.copytree(Path(path_helper.get_iblrig_folder()) / "pybpod_fixtures", path_helper.get_iblrig_params_folder(),
                        dirs_exist_ok=True)

    # start pybpod
    from pybpodgui_plugin.__main__ import start as start_pybpod
    start_pybpod()
