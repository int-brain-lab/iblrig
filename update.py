#!/usr/bin/python3
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
"""
Usage:
    update.py
        Will fetch changes from origin. Nothing is updated yet!
        Calling update.py will display information on the available versions
    update.py -h | --help | ?
        Displays this docstring.
    update.py <version>
        Will checkout the <version> release and import task files to pybpod.
    update.py <branch>
        Will checkout the latest commit of <branch> and import task files to
        pybpod.
    update.py reinstall
        Will reinstall the rig to the latest revision on master.
    update.py ibllib
        Will reset ibllib to latest revision on master and install to iblenv.
    update.py update
        Will update itself to the latest revision on master.
    update.py update <branch>
        Will update itself to the latest revision on <branch>.
"""
import os
import subprocess
from pathlib import Path
import argparse

from setup_default_config import (copy_code_files_to_iblrig_params,
                                  update_pybpod_config)


def get_versions():
    vers = subprocess.check_output(["git", "ls-remote",
                                    "--tags", "origin"]).decode().split()
    vers = [x for x in vers[1::2] if '{' not in x]
    vers = [x.split('/')[-1] for x in vers]
    available = [x for x in vers if x >= '3.6.0']
    print("Available versions: {}".format(available))
    return vers


def get_branches():
    branches = subprocess.check_output(["git", "ls-remote",
                                        "--heads", "origin"]).decode().split()
    branches = [x.split('heads')[-1] for x in branches[1::2]]
    branches = [x[1:] for x in branches]
    print("Available branches: {}".format(branches))

    return branches


def get_current_branch():
    branch = subprocess.check_output(
        ['git', 'branch', '--points-at', 'HEAD']).decode().strip().strip('* ')
    print("Current branch: {}".format(branch))
    return branch


def get_current_version():
    tag = subprocess.check_output(["git", "tag",
                                   "--points-at", "HEAD"]).decode().strip()
    print("Current version: {}".format(tag))
    return tag


def pull(branch):
    subprocess.call(['git', 'pull', 'origin', branch])


def fetch():
    subprocess.call(['git', 'fetch', '--all'])


def iblrig_params_path():
    return str(Path(os.getcwd()).parent / 'iblrig_params')


def import_tasks():
    if VERSION > '3.3.0' or get_current_branch() == 'develop':
        update_pybpod_config(iblrig_params_path())
    copy_code_files_to_iblrig_params(iblrig_params_path(),
                                     exclude_filename=None)


def checkout_version(ver):
    print("\nChecking out {}".format(ver))
    subprocess.call(["git", "reset", "--hard"])
    subprocess.call(['git', 'checkout', 'tags/' + ver])
    pull(f'tags/{ver}')


def checkout_branch(branch):
    print("\nChecking out {}".format(branch))
    subprocess.call(['git', 'checkout', branch])
    subprocess.call(["git", "reset", "--hard"])
    pull(branch)


def checkout_single_file(file=None, branch='master'):
    subprocess.call("git checkout origin/{} -- {}".format(branch,
                                                          file).split())

    print("Checked out", file, "from branch", branch)


def update_remotes():
    subprocess.call(['git', 'remote', 'update'])


def update_env():
    print("\nUpdating iblenv")
    os.system("pip install -r requirements.txt --upgrade --user")  # noqa


def update_conda():
    os.system("conda update -y -n base conda")


def update_pip():
    os.system("pip install --user --upgrade pip setuptools wheel")


def update_ibllib():
    new_install_location = IBLRIG_ROOT_PATH / 'src' / 'ibllib'
    old_install_location = IBLRIG_ROOT_PATH.parent / 'ibllib'

    if new_install_location.exists():
        os.chdir(new_install_location)
        subprocess.call(["git", "reset", "--hard"])
        subprocess.call(["git", "pull"])

    if old_install_location.exists():
        os.chdir(old_install_location)
        subprocess.call(["git", "reset", "--hard"])
        subprocess.call(["git", "pull"])

    os.chdir(IBLRIG_ROOT_PATH)


def branch_info():
    print("Current availiable branches:")
    print(subprocess.check_output(["git", "branch", "-avv"]).decode())


def info():
    update_remotes()
    # branch_info()
    ver = VERSION
    versions = ALL_VERSIONS
    if not ver:
        print("WARNING: You appear to be on an untagged commit.",
              "\n         Try updating to a specific version")
    else:
        idx = sorted(versions).index(ver) if ver in versions else 0
        if idx + 1 == len(versions):
            print("The version you have checked out is the latest version\n")
        else:
            print("Newest version |{}| type:\n\npython update.py {}\n".format(
                sorted(versions)[-1], sorted(versions)[-1]))


def ask_user_input(msg="Do you want to update?", responses=['y', 'n']):
    use_msg = msg + f' {responses}: '
    response = input(use_msg)
    if response not in responses:
        print(f"Acceptable answers: {responses}")
        return ask_user_input(msg=msg, responses=responses)

    return response


def update_to_latest():
    ver = VERSION
    versions = ALL_VERSIONS
    idx = sorted(versions).index(ver) if ver in versions else 0
    if idx + 1 == len(versions):
        return
    else:
        _update()


def _update(branch=None, version=None):
    resp = ask_user_input()
    if resp == 'y':
        if branch:
            checkout_branch(branch)
        elif version:
            checkout_version(version)
        elif branch is None and version is None:
            checkout_version(sorted(ALL_VERSIONS)[-1])
        update_env()
        import_tasks()
        update_ibllib()
    else:
        return


def main(args):
    nargs_passed = sum([True for x in args.__dict__.values() if x])

    if not any(args.__dict__.values()):
        update_to_latest()

    if nargs_passed == 2:
        if args.update and args.b:
            if args.b not in ALL_BRANCHES:
                print('Not found:', args.b)
                return
            checkout_single_file(file='update.py', branch=args.b)
        else:
            print(NotImplemented)
        return
    elif nargs_passed == 1:
        if args.b and args.b in ALL_BRANCHES:
            _update(branch=args.b)
        elif args.b and args.b not in ALL_BRANCHES:
            print('Branch', args.b, 'not found')

        if args.update:
            checkout_single_file(file='update.py', branch='master')

        if args.v and args.v in ALL_VERSIONS:
            _update(version=args.v)
        elif args.v and args.v not in ALL_VERSIONS:
            print('Version', args.v, 'not found')

        if args.reinstall:
            os.system("conda deactivate && python install.py")

        if args.ibllib:
            update_ibllib()

        if args.info:
            info()

        if args.import_tasks:
            import_tasks()

        if args.iblenv:
            update_env()

        if args.conda_pip:
            update_pip()
            update_conda()

        return


if __name__ == '__main__':
    IBLRIG_ROOT_PATH = Path.cwd()
    fetch()
    update_pip()
    ALL_BRANCHES = get_branches()
    ALL_VERSIONS = get_versions()
    BRANCH = get_current_branch()
    VERSION = get_current_version()
    parser = argparse.ArgumentParser(description='Install iblrig')
    parser.add_argument('-v', required=False, default=False,
                        help='Available versions: ' + str(ALL_VERSIONS))
    parser.add_argument('-b', required=False, default=False,
                        help='Available branches: ' + str(ALL_BRANCHES))
    parser.add_argument('--reinstall', required=False, default=False,
                        action='store_true', help='Reinstall iblrig')
    parser.add_argument('--ibllib', required=False, default=False,
                        action='store_true', help='Update ibllib only')
    parser.add_argument('--update', required=False, default=False,
                        action='store_true', help='Update self: update.py')
    parser.add_argument('--info', required=False, default=False,
                        action='store_true',
                        help='Disply information on branches and versions')
    parser.add_argument('--iblenv', required=False, default=False,
                        action='store_true', help='Update iblenv only')
    parser.add_argument('--import-tasks', required=False, default=False,
                        action='store_true', help='Reimport tasks only')
    parser.add_argument('--conda-pip', required=False, default=False,
                        action='store_true', help='Update conda and pip')
    args = parser.parse_args()
    main(args)
    print('\n')
