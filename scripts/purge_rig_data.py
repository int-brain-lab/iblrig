#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, March 28th 2019, 7:53:44 pm
"""
Purge data from RIG
- Find all files by rglob
- Find all sessions of the found files
- Check Alyx if corresponding datasetTypes have been registered as existing
sessions and files on Flatiron
- Delete local raw file if found on Flatiron
"""
from ibllib.pipes.purge_rig_data import purge_local_data
import logging
import argparse

log = logging.getLogger("iblrig")
log.setLevel(logging.INFO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete files from rig")
    parser.add_argument("folder", help="Local iblrig_data folder")
    parser.add_argument("file", help="File name to search and destroy for every session")
    parser.add_argument(
        "-lab",
        required=False,
        default=None,
        help="Lab name, search on Alyx faster. default: None",
    )
    parser.add_argument(
        "--dry",
        required=False,
        default=False,
        action="store_true",
        help="Dry run? default: False",
    )
    args = parser.parse_args()
    purge_local_data(args.folder, args.file, lab=args.lab, dry=args.dry)
    print("Done\n")
