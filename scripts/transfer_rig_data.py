#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, July 4th 2019, 1:37:34 pm
from ibllib.pipes.transfer_rig_data import main
import logging
import argparse

log = logging.getLogger("iblrig")
log.setLevel(logging.INFO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer files to IBL local server")
    parser.add_argument("local_folder", help="Local iblrig_data/Subjects folder")
    parser.add_argument("remote_folder", help="Remote iblrig_data/Subjects folder")
    args = parser.parse_args()
    main(args.local_folder, args.remote_folder)
