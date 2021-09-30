#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: iblrig/update.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Saturday, August 10th 2019, 10:31:02 am
import argparse
from pathlib import Path
import iblrig.git as git


if __name__ == "__main__":
    IBLRIG_ROOT_PATH = Path.cwd()
    git.fetch()
    ALL_BRANCHES = git.get_branches()
    ALL_VERSIONS = git.get_versions()
    BRANCH = git.get_current_branch()
    VERSION = git.get_current_version()
    parser = argparse.ArgumentParser(description="Update iblrig")
    parser.add_argument(
        "-v", required=False, default=False, help="Available versions: " + str(ALL_VERSIONS),
    )
    parser.add_argument(
        "-b", required=False, default=False, help="Available branches: " + str(ALL_BRANCHES),
    )
    parser.add_argument(
        "--reinstall", required=False, default=False, action="store_true", help="Reinstall iblrig",
    )
    parser.add_argument(
        "--ibllib", required=False, default=False, action="store_true", help="Update ibllib only",
    )
    parser.add_argument(
        "--update",
        required=False,
        default=False,
        action="store_true",
        help="Update self: update.py",
    )
    parser.add_argument(
        "--info",
        required=False,
        default=False,
        action="store_true",
        help="Disply information on branches and versions",
    )
    parser.add_argument(
        "--iblenv", required=False, default=False, action="store_true", help="Update iblenv only",
    )
    parser.add_argument(
        "--setup-pybpod",
        required=False,
        default=False,
        action="store_true",
        help="Reset pybpod to default config",
    )
    parser.add_argument(
        "--conda", required=False, default=False, action="store_true", help="Update conda",
    )
    parser.add_argument(
        "--pip",
        required=False,
        default=False,
        action="store_true",
        help="Update pip setuptools and wheel",
    )
    parser.add_argument(
        "--upgrade-conda",
        required=False,
        default=False,
        action="store_true",
        help="Dont update conda",
    )
    parser.add_argument(
        "--upgrade-bonsai",
        required=False,
        default=False,
        action="store_true",
        help="Upgrade Bonsai",
    )
    parser.add_argument(
        "--update-exists",
        required=False,
        default=False,
        action="store_true",
        help="Check if new version of rig code exists",
    )
    args = parser.parse_args()

    from iblrig._update import main

    main(args)
    print("\n")
