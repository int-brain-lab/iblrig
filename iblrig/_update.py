#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
"""
usage: update.py [-h] [-v V] [-b B] [--reinstall] [--ibllib] [--update]
                 [--info] [--iblenv] [--import-tasks] [--conda] [--pip]
                 [--upgrade-conda]

Update iblrig

optional arguments:
  -h, --help       show this help message and exit
  -v V             Available versions: ['1.0.0', '1.1.0', '1.1.1', '1.1.2',
                   '1.1.3', '1.1.4', '1.1.5', '1.1.6', '1.1.7', '1.1.8',
                   '2.0.0', '2.0.1', '3.0.0', '3.1.0', '3.1.1', '3.2.0',
                   '3.2.1', '3.2.2', '3.2.3', '3.2.4', '3.3.0', '3.4.0',
                   '3.4.1', '3.5.0', '3.5.1', '3.5.2', '3.5.3', '3.5.4',
                   '3.6.0', '3.7.0', '3.7.1', '3.7.2', '3.7.3', '3.7.4',
                   '3.7.5', '3.7.6', '3.8.0', '3.8.1', '4.0.0', '4.0.1',
                   '4.1.0', '4.1.1', '4.1.2', '4.1.3', '5.0.0']
  -b B             Available branches: ['develop',
                   'feature/screen_calibration', 'install_test', 'master']
  --reinstall      Reinstall iblrig
  --ibllib         Update ibllib only
  --update         Update self: update.py
  --info           Disply information on branches and versions
  --iblenv         Update iblenv only
  --import-tasks   Reimport tasks only
  --conda          Update conda
  --pip            Update pip setuptools and wheel
  --upgrade-conda  Dont update conda
"""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

from setup_default_config import main as setup_pybpod


def get_versions():
    vers = subprocess.check_output(["git", "ls-remote",
                                    "--tags", "origin"]).decode().split()
    vers = [x for x in vers[1::2] if '{' not in x]
    vers = [x.split('/')[-1] for x in vers]
    broken = ['6.3.0', '6.3.1']
    available = [x for x in vers if x >= '6.2.5' and x not in broken]
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
    setup_pybpod(iblrig_params_path())


def checkout_version(ver):
    print("\nChecking out {}".format(ver))
    subprocess.call(["git", "reset", "--hard"])
    subprocess.call(['git', 'checkout', 'tags/' + ver])
    pull(f'tags/{ver}')


def checkout_branch(branch):
    print("\nChecking out {}".format(branch))
    subprocess.call(["git", "reset", "--hard"])
    subprocess.call(['git', 'checkout', branch])
    pull(branch)


def checkout_single_file(file=None, branch='master'):
    subprocess.call("git checkout origin/{} -- {}".format(branch,
                                                          file).split())

    print("Checked out", file, "from branch", branch)


def update_remotes():
    subprocess.call(['git', 'remote', 'update'])


def update_env():
    print("\nUpdating iblenv")
    os.system("pip install -r requirements.txt -U")
    os.system("pip install -e .")


def update_conda():
    print('\nCleaning cache')
    os.system("conda clean -a -y")
    print("\nUpdating conda")
    os.system("conda update -y -n base conda")


def update_pip():
    print("\nUpdating pip et al.")
    os.system("pip install -U setuptools wheel")
    os.system("python -m pip install --upgrade pip")


def update_ibllib():
    os.system("pip install ibllib -U")


def update_bonsai_config():
    print("\nUpdating Bonsai")
    broot = IBLRIG_ROOT_PATH / 'Bonsai'
    subprocess.call([str(broot / 'Bonsai.exe'), '--no-editor'])
    print('Done')


def remove_bonsai():
    broot = IBLRIG_ROOT_PATH / 'Bonsai'
    shutil.rmtree(broot)

def upgrade_bonsai(version, branch):
    print("\nUpgrading Bonsai")
    remove_bonsai()
    if not version:
        checkout_branch(branch)
    elif not branch:
        checkout_version(version)


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


def ask_user_input(ver='#.#.#', responses=['y', 'n']):
    msg = f"Do you want to update to {ver}?"
    use_msg = msg.format(ver) + f' ([{responses[0]}], {responses[1]}): '
    response = input(use_msg) or 'y'
    if response not in responses:
        print(f"Acceptable answers: {responses}")
        return ask_user_input(ver=ver, responses=responses)

    return response


def update_to_latest():
    ver = VERSION
    versions = ALL_VERSIONS
    idx = sorted(versions).index(ver) if ver in versions else 0
    if idx + 1 == len(versions):
        return
    else:
        _update(version=versions[-1])

# %% THIS guy!!!
def _update(branch=None, version=None):
    ver = branch or version
    resp = ask_user_input(ver=ver)
    if resp == 'y':
        if branch:
            checkout_branch(branch)
        elif version:
            checkout_version(version)
        elif branch is None and version is None:
            checkout_version(sorted(ALL_VERSIONS)[-1])
        update_pip()
        update_env()
        import_tasks()
        if UPGRADE_BONSAI:
            upgrade_bonsai(version, branch)
        update_bonsai_config()
    else:
        return


def main(args):
    if not any(args.__dict__.values()):
        update_to_latest()

    if args.update:
        checkout_single_file(file='update.py', branch='master')

    if args.update and args.b:
        if args.b not in ALL_BRANCHES:
            print('Not found:', args.b)
            return
        checkout_single_file(file='update.py', branch=args.b)

    if args.b and args.b in ALL_BRANCHES:
        _update(branch=args.b)
    elif args.b and args.b not in ALL_BRANCHES:
        print('Branch', args.b, 'not found')

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

    if args.pip:
        update_pip()

    if args.conda:
        update_conda()

    if args.upgrade_bonsai:
        upgrade_bonsai(VERSION, BRANCH)
        update_bonsai_config()

    return


if __name__ == '__main__':
    IBLRIG_ROOT_PATH = Path.cwd()
    fetch()
    ALL_BRANCHES = get_branches()
    ALL_VERSIONS = get_versions()
    BRANCH = get_current_branch()
    VERSION = get_current_version()
    UPGRADE_BONSAI = True if list(Path().glob('upgrade_bonsai')) else False
    parser = argparse.ArgumentParser(description='Update iblrig')
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
    parser.add_argument('--conda', required=False, default=False,
                        action='store_true', help='Update conda')
    parser.add_argument('--pip', required=False, default=False,
                        action='store_true',
                        help='Update pip setuptools and wheel')
    parser.add_argument('--upgrade-conda', required=False, default=False,
                        action='store_true', help='Dont update conda')
    parser.add_argument('--upgrade-bonsai', required=False, default=False,
                        action='store_true', help='Upgrade Bonsai')
    args = parser.parse_args()

    main(args)
    print('\n')
