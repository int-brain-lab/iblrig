"""
Script used to copy the requisite files, from the pybpod_fixtures dir, for pybpod to launch. Files should be copied to the dir
'C:\\iblrig_params' on a production system, pybpod will then need to be run from that directory.
"""
import shutil
from pathlib import Path

import iblrig.path_helper as path_helper

if __name__ == "__main__":
    iblrig_params_path = Path(path_helper.get_iblrig_params_folder())
    print(f"Trying to copy pybpod files to {iblrig_params_path} ... ")
    try:
        shutil.copytree(Path(path_helper.get_iblrig_folder()) / "pybpod_fixtures", path_helper.get_iblrig_params_folder(),
                        dirs_exist_ok=False)
    except FileExistsError as msg:
        print(msg)
        print(f"The {iblrig_params_path} directory already exists. Please backup this directory if any custom tasks or "
              f"configurations exist. Then remove or rename the directory. Pay special attention to the '.iblrig_params.json' "
              f"file typically found in this directory.")
