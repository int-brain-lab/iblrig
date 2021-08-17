#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: scripts/create_custom_project_from_alyx.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Tuesday, August 17th 2021, 5:21:16 pm
import iblrig.pybpod_config as pc
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create custom project, users, and subjects from Alyx"
    )
    parser.add_argument("project_name", help="Name of existing Alyx project")
    args = parser.parse_args()
    pc.create_custom_project_from_alyx(args.project_name)
