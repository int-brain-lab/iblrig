#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-06-12 13:32:59
"""
Usage:
    update.py
        Will pull the latest revision of IBL_root current branch
    update.py   upgrade
        Will pull the latest revision of IBL_root default branch

"""
import subprocess
import os
import sys

# git symbolic-ref HEAD --> refs/heads/master
# git rev-parse --abbrev-ref HEAD --> master
# git symbolic-ref --short HEAD --> master
# git name-rev --name-only HEAD --> master
branch = subprocess.check_output(["git", "branch"]).decode()
branch[branch.find('*'):].strip().split('*')[-1].strip()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("update()")
        # update()
    elif len(sys.argv) == 2:
        if sys.argv[1] == 'upgrade':
            print("upgrade()")
            # upgrade()
        else:
            print("Command unknown", __doc__)
