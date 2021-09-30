#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, July 4th 2019, 1:37:34 pm
import argparse
import logging
import os
from pathlib import Path

from ibllib.pipes.transfer_rig_data import main

log = logging.getLogger("iblrig")
log.setLevel(logging.INFO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer files to IBL local server")
    parser.add_argument("local_folder", help="Local iblrig_data/Subjects folder")
    parser.add_argument("remote_folder", help="Remote iblrig_data/Subjects folder")
    args = parser.parse_args()
    scripts_path = Path(__file__).absolute().parent
    os.system(f"python {scripts_path / 'move_passive.py'}")
    main(args.local_folder, args.remote_folder)
