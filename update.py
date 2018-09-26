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
        Will backup pybpod_projects folder where local configurations live.
        Will checkout the <version> release, update the submodules, and restore
        the pybpod_projects folder from backup.
    update.py tasks
        Will checkout any task file not present in the local tasks folder.
    update.py tasks <branch>
        Will checkout any task file from <branch> not present in local folder.
    update.py -h | --help | ?
        Displays this docstring.
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path


def get_versions():
    vers = subprocess.check_output(["git", "ls-remote",
                                    "--tags", "origin"]).decode().split()
    vers = [x for x in vers[1::2] if '{' not in x]
    vers = [x.split('/')[-1] for x in vers]
    print("\nAvailable versions: {}\n".format(vers))
    return vers


def get_branches():
    branches = subprocess.check_output(["git", "ls-remote",
                                    "--heads", "origin"]).decode().split()
    branches = [x.split('heads')[-1] for x in branches[1::2]]
    branches = [x[1:] for x in branches]
    print("\nAvailable versions: {}\n".format(branches))

    return branches


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


def get_new_tasks(branch='master'):
    print("Checking for new tasks:")
    local_tasks_dir = os.path.join(
        os.getcwd(), 'pybpod_projects', 'IBL', 'tasks')

    ltp = Path(local_tasks_dir)
    local_tasks = [str(x).split(os.sep)[-1]
                   for x in ltp.glob('*') if x.is_dir()]

    subprocess.call("git fetch".split())
    all_files = subprocess.check_output(
        "git ls-tree -r --name-only origin/{}".format(
            branch).split()).decode().split('\n')

    remote_task_files = [x for x in all_files if 'tasks' in x]

    found_files = []
    for lt in local_tasks:
        found_files.extend([x for x in remote_task_files if lt in x])

    missing_files = list(set(remote_task_files) - set(found_files))
    # Remove tasks.json file
    missing_files = [x for x in missing_files if "tasks.json" not in x]
    print("Found {} new files:".format(len(missing_files)))
    print(missing_files)

    return missing_files


def checkout_missing_task_files(missing_files, branch='master'):
    for file in missing_files:
        subprocess.call("git checkout origin/{} -- {}".format(branch,
                                                                file).split())
        print("Checked out:", file)
    print("Done.")


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
            missing_files = get_new_tasks(branch='master')
            checkout_missing_task_files(missing_files, branch='master')
        else:
            print("Unknown version...")
    elif len(sys.argv) == 3:
        if sys.argv[1] != 'tasks':
            print("Unknown command...")
        elif sys.argv[2] in get_branches():
            missing_files = get_new_tasks(branch=sys.argv[2])
            checkout_missing_task_files(missing_files, branch=sys.argv[2])

    print("Done")
