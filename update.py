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
    update.py <version>
        Will checkout the <version> release and update the submodules
    update.py -h | --help | ?
        Displays this docstring.
"""
import subprocess
import sys
import os
import shutil


def get_versions():
    vers = subprocess.check_output(["git", "ls-remote",
                                    "--tags", "origin"]).decode().split()
    vers = [x for x in vers[1::2] if '{' not in x]
    vers = [x.split('/')[-1] for x in vers]
    print("\nAvailable versions: {}\n".format(vers))
    return vers


def get_current_version():
    tag = subprocess.check_output(["git", "tag",
                                   "--points-at", "HEAD"]).decode().strip()
    print("\nCurrent version: {}\n".format(tag))
    return tag


def submodule_update():
    print("Running: git submodule update")
    subprocess.call(['git', 'submodule', 'update'])


def pull():
    subprocess.call(['git', 'pull', 'origin', 'master'])
    submodule_update()


def pybpod_projects_path():
    return os.path.join(os.getcwd(), 'pybpod_projects')


def backup_pybpod_projects():
    print("Backing up current pybpod_projects configuration")
    src = pybpod_projects_path()
    dst = os.path.join(os.path.expanduser('~'), 'pybpod_projects.bk')
    shutil.copytree(src, dst,
        ignore=shutil.ignore_patterns('sessions'))


def restore_pybpod_projects_from_backup():
    print("Restoring pybpod_projects")
    src = os.path.join(os.path.expanduser('~'), 'pybpod_projects.bk')
    dst = os.getcwd()
    shutil.rmtree(os.path.join(os.getcwd(), 'pybpod_projects'))
    shutil.move(src, dst)
    os.rename(os.path.join(os.getcwd(), 'pybpod_projects.bk'),
              pybpod_projects_path())


def get_new_tasks():
    print("Checking for new tasks:")
    "git fetch"
    "git ls-tree -r --name-only origin/master | grep tasks"
    if condition:
        print("No new task found.")
    else:
        print("Downloading new task(s):")
        # Check latest master and find new tasks
        "git checkout origin/develop - - pybpod_projects/IBL/tasks/tasks.json"

def checkout_version(ver):
    print("\nChecking out {}".format(ver))
    subprocess.call(['git', 'checkout', 'tags/' + ver])
    submodule_update()


def update_remotes():
    print("Getting info on remote branches from origin")
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
        print("WARNING: You appear to be on an untagged release.")
        print("Try updating to a specific version\n")
    else:
        idx = sorted(versions).index(ver) if ver in versions else None
        if idx + 1 == len(versions):
            print("\nThe version you have checked out is the latest version\n")
        else:
            print("Newest version |{}| type:\n\npython update.py {}\n".format(
                sorted(versions)[-1], sorted(versions)[-1]))


if __name__ == '__main__':
    if len(sys.argv) == 1:
        info()
    elif len(sys.argv) == 2:
        help_args = ['-h', '--help', '?']
        if sys.argv[1] in help_args:
            print(__doc__)
        elif sys.argv[1] in get_versions():
            backup_pybpod_projects()
            checkout_version(sys.argv[1])
            restore_pybpod_projects_from_backup()
        elif sys.argv[1] == 'tasks':
            get_new_tasks()
        else:
            print("Unknown version...")
    print("Done")
