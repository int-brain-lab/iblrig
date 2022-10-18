"""
Script used to test that pybpod launches with the given test data in the fixtures dir; ensure when running this script that the
iblrig_params dir already exists and that the script is executed from that dir (required for pybpod functionality)
"""
import argparse
import os
import shutil
from pathlib import Path
import iblrig.path_helper as ph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup iblpybpod")
    parser.add_argument("-t", "--test", action="store_true", help="Removes local iblrig_params dir and copies test data")
    args = parser.parse_args()

    if args.test:
        for name in os.listdir(ph.get_iblrig_params_folder()):  # delete the contents of the ibl_params dir (pybpod dir)
            full_path = Path(ph.get_iblrig_params_folder()) / name
            shutil.rmtree(full_path) if Path(full_path).is_dir() else os.unlink(full_path)

        # Copy test data content to ibl_params dir (pybpod dir)
        shutil.copytree(Path(ph.get_iblrig_folder()) / "test_iblrig" / "fixtures" / "test_iblrig_params",
                        ph.get_iblrig_params_folder(), dirs_exist_ok=True)

    # start pybpod
    from pybpodgui_plugin.__main__ import start as start_pybpod
    start_pybpod()
