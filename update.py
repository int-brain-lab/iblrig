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
    update.py <branch_name>
        Will pull <branch_name> from origin if exists
"""
import subprocess
import os
import sys


def get_current_branch():
    curr_branch = subprocess.check_output(['git', 'symbolic-ref', '--short',
                                           'HEAD'])
    curr_branch = curr_branch.decode().strip()
    return curr_branch


def get_remote_branches():
    remote_branches = subprocess.check_output(['git', 'branch', '-r'
                                               ]).decode().split()
    return remote_branches


def get_default_remote_branch():
    remote_branches = get_remote_branches()
    if 'origin/master' in remote_branches:
        return 'master'
    elif 'origin/HEAD' in remote_branches:
        default = subprocess.check_output(['git' 'branch' '-r' '--points-at'
                                           'origin/HEAD']).decode().split()[-1]
        return default.split('/')[-1]


def check_branch(branch):
    if 'origin/' + branch not in remote_branches:
        print("Branch {} does not exist on remote".format(branch))
        return


def update(branch):
    subprocess.call(['git', 'pull', 'origin', branch])


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("update(CURR_BRANCH)")
        # update(CURR_BRANCH)
    elif len(sys.argv) == 2:
        if sys.argv[1] == 'upgrade':
            print("upgrade()")
            # upgrade()
        else:
            branch = sys.argv[1]
            if 'origin/' + branch in remote_branches:
                print("update(branch)")
            else:
                print("Branch {} does not exist on remote".format(branch))
