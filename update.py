#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-07-12 17:10:22
"""
Usage:
    update.py
        Will fetch changes from origin. Nothing is updated yet!
        Calling update.py will display information on the available versions
    update.py -h | --help | ?
        Displays this docstring.
    update.py <version>
        Will checkout the <version> release and import the task files to pybpod.
    update.py <branch>
        Will checkout the latest commit of <branch> and import the task files to pybpod.
    update.py reinstall
        Will reinstall the rig to the latest revision on master.
    update.py update
        Will update itself to the latest revision on master.
    update.py update <branch>
        Will update itself to the latest revision on <branch>.
    update.py tasks
        Will reimport tasks to pybpod with overwriting task_settings.py.
    update.py tasks <branch>
        Will checkout latest revision of <branch> and import tasks overwriting task_settings.py.


"""
import subprocess
import sys
import os
import shutil
from pathlib import Path
from setup_default_config import copy_code_files_to_iblrig_params


def get_versions():
    vers = subprocess.check_output(["git", "ls-remote",
                                    "--tags", "origin"]).decode().split()
    vers = [x for x in vers[1::2] if '{' not in x]
    vers = [x.split('/')[-1] for x in vers]
    available = [x for x in vers if x >= '2.0.0']
    print("\nAvailable versions: {}\n".format(available))
    return vers


def get_branches():
    branches = subprocess.check_output(["git", "ls-remote",
                                        "--heads", "origin"]).decode().split()
    branches = [x.split('heads')[-1] for x in branches[1::2]]
    branches = [x[1:] for x in branches]
    print("\nAvailable branches: {}\n".format(branches))

    return branches


def get_current_version():
    tag = subprocess.check_output(["git", "tag",
                                   "--points-at", "HEAD"]).decode().strip()
    print("\nCurrent version: {}".format(tag))
    return tag


def submodule_update():
    print("Running: git submodule update")
    subprocess.call(['git', 'submodule', 'update'])


def pull():
    subprocess.call(['git', 'pull', 'origin', 'master'])
    submodule_update()


def iblrig_params_path():
    return str(Path(os.getcwd()).parent / 'iblrig_params')


def import_tasks():
    copy_code_files_to_iblrig_params(iblrig_params_path(),
                                     exclude_filename='task_settings.py')


def import_tasks_with_settings():
    copy_code_files_to_iblrig_params(iblrig_params_path(),
                                     exclude_filename=None)


def checkout_version(ver):
    print("\nChecking out {}".format(ver))
    subprocess.call(['git', 'checkout', 'tags/' + ver])


def checkout_branch(ver):
    print("\nChecking out {}".format(ver))
    subprocess.call(['git', 'checkout', ver])


def checkout_single_file(file=None, branch='master'):
    subprocess.call("git checkout origin/{} -- {}".format(branch,
                                                          file).split())

    print("Checked out", file, "from branch", branch)


def update_remotes():
    subprocess.call(['git', 'remote', 'update'])


def branch_info():
    print("Current availiable branches:")
    print(subprocess.check_output(["git", "branch", "-avv"]).decode())


def info():
    update_remotes()
    # branch_info()
    ver = get_current_version()
    versions = get_versions()
    if not ver:
        print("WARNING: You appear to be on an untagged release.",
              "\n         Try updating to a specific version")
        print()
    else:
        idx = sorted(versions).index(ver) if ver in versions else None
        if idx + 1 == len(versions):
            print("\nThe version you have checked out is the latest version\n")
        else:
            print("Newest version |{}| type:\n\npython update.py {}\n".format(
                sorted(versions)[-1], sorted(versions)[-1]))


if __name__ == '__main__':
    # TODO: Use argparse!!
    # If called alone
    if len(sys.argv) == 1:
        info()
    # If called with something in front
    elif len(sys.argv) == 2:
        versions = get_versions()
        branches = get_branches()
        help_args = ['-h', '--help', '?']
        # HELP
        if sys.argv[1] in help_args:
            print(__doc__)
        # UPDATE TO VERSION
        elif sys.argv[1] in versions:
            checkout_version(sys.argv[1])
            import_tasks()
        elif sys.argv[1] in branches:
            checkout_branch(sys.argv[1])
            import_tasks()
        # UPDATE UPDATE
        elif sys.argv[1] == 'update':
            checkout_single_file(file='update.py', branch='master')
        # UPDATE REINSTALL
        elif sys.argv[1] == 'reinstall':
            subprocess.call(['python', 'install.py'])
        elif sys.argv[1] == 'tasks':
            import_tasks_with_settings()
        # UNKNOWN COMMANDS
        else:
            print("ERROR:", sys.argv[1],
                  "is not a  valid command or version number.")
            raise ValueError
    # If called with something in front of something in front :P
    elif len(sys.argv) == 3:
        branches = get_branches()
        commands = ['update', 'tasks']
        # Command checks
        if sys.argv[1] not in commands:
            print("ERROR:", "Unknown command...")
            raise ValueError
        if sys.argv[2] not in branches:
            print("ERROR:", sys.argv[2], "is not a valid branch.")
            raise ValueError
        # Commands
        if sys.argv[1] == 'update' and sys.argv[2] in branches:
            checkout_single_file(file='update.py', branch=sys.argv[2])
        elif sys.argv[1] == 'tasks' and sys.argv[2] in branches:
            checkout_branch(sys.argv[2])
            import_tasks_with_settings()
    print("\n")
