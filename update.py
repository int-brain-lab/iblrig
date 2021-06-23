"""
Filename: c:\iblrig\update.py
Path: c:\iblrig
Created Date: Tuesday, August 4th 2020, 5:29:26 pm
Author: Niccolo' Bonacchi

Copyright (c) 2021 Your Company
"""
import argparse
import subprocess
from pathlib import Path


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

    from iblrig._update import main
    main(args)
    print('\n')
