#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-07-05 16:14:33
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
        default = subprocess.check_output(['git', 'branch', '-r', '--points-at',
                                           'origin/HEAD']).decode().split()[-1]
        return default.split('/')[-1]


def check_branch(branch):
    if 'origin/' + branch not in get_remote_branches():
        print("Branch not found on remote: {}".format(branch))
        return 1
    else:
        return 0


def submodule_update():
    print("Running: git submodule update")
    subprocess.call(['git', 'submodule', 'update'])


def update(branch):
    print("Running update: git pull origin {}".format(branch))
    subprocess.call(['git', 'pull', 'origin', branch])
    submodule_update()


def upgrade():
    print("Checking for upgrades...")
    branch = get_current_branch()
    default_remote_branch = get_default_remote_branch()
    if default_remote_branch == branch:
        print("No new version found: updating to latest patch of {}".format(branch))
        update(branch)
    else:
        print("New version found: updating to {}".format(default_remote_branch))
        subprocess.call(['git', 'checkout', default_remote_branch])
        update(get_current_branch())


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("update({})".format(get_current_branch()))
        update(get_current_branch())
        pass
    elif len(sys.argv) == 2:
        help_args = ['-h', '--help', '?']
        if sys.argv[1] in help_args:
            print(__doc__)
            pass
        elif sys.argv[1] == 'upgrade':
            print("upgrade()")
            upgrade()
        else:
            branch = sys.argv[1]
            if check_branch(branch):
                pass
            else:
                subprocess.call(['git', 'checkout', branch])
                update(branch)

        pass
    print("Done!")
