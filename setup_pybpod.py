"""
Script used to copy the requisite files, from the pybpod_fixtures dir, for pybpod to launch. Files should be copied to the dir
'C:\\iblrig_params' on a production system, pybpod will then need to be run from that directory.
"""
import argparse
import shutil
from pathlib import Path

import iblrig.path_helper as path_helper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup pybpod")
    parser.add_argument("-g", "--github_actions", action="store_true", help="Use github actions ci friendly paths")
    args = parser.parse_args()

    if args.github_actions:
        iblrig_params_path = Path().absolute().parent / "iblrig_params"
        pybpod_fixtures_path = Path().absolute() / "pybpod_fixtures"
    else:
        iblrig_params_path = Path(path_helper.get_iblrig_params_folder())
        pybpod_fixtures_path = Path(path_helper.get_iblrig_folder()) / "pybpod_fixtures"

    print(f"Trying to copy pybpod files to {iblrig_params_path} ... ")
    try:
        shutil.copytree(pybpod_fixtures_path, iblrig_params_path, dirs_exist_ok=False)
        print("Files for pybpod copied successfully.")
    except FileExistsError as msg:
        print(msg)
        print(f"The {iblrig_params_path} directory already exists. Please backup this directory if any custom tasks or "
              f"configurations exist. Then remove or rename the directory. Pay special attention to the '.iblrig_params.json' "
              f"file typically found in this directory.")
