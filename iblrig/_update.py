#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
import os
import shutil
import subprocess
from pathlib import Path

from setup_default_config import main as setup_pybpod

import iblrig.git as git


IBLRIG_ROOT_PATH = Path.cwd()
git.fetch()
ALL_BRANCHES = git.get_branches()
ALL_VERSIONS = git.get_versions()
BRANCH = git.get_current_branch()
VERSION = git.get_current_version()
UPGRADE_BONSAI = True if list(Path().glob("upgrade_bonsai")) else False


def iblrig_params_path():
    return str(Path(os.getcwd()).parent / "iblrig_params")


def import_tasks():
    setup_pybpod(iblrig_params_path())


def update_env():
    print("\nUpdating iblenv")
    os.system("pip install -r requirements.txt -U")
    os.system("pip install -e .")


def update_conda():
    print("\nCleaning cache")
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
    broot = IBLRIG_ROOT_PATH / "Bonsai"
    subprocess.call([str(broot / "Bonsai.exe"), "--no-editor"])
    print("Done")


def remove_bonsai():
    broot = IBLRIG_ROOT_PATH / "Bonsai"
    shutil.rmtree(broot)


def upgrade_bonsai(version, branch):
    print("\nUpgrading Bonsai")
    remove_bonsai()
    if not version:
        git.checkout_branch(branch)
    elif not branch:
        git.checkout_version(version)
    here = os.getcwd()
    os.chdir(os.path.join(IBLRIG_ROOT_PATH, "Bonsai"))
    subprocess.call("setup.bat")
    os.chdir(here)


def info():
    print("--")
    git.update_remotes()
    # git.branch_info()
    git.get_branches(verbose=True)
    git.get_versions(verbose=True)
    print("--")
    print("Current branch: {}".format(BRANCH))
    print("Current version: {}".format(VERSION))
    print("--")
    ver = VERSION
    versions = ALL_VERSIONS
    if not ver:
        print(
            "\nWARNING: You appear to be on an untagged commit.",
            "\n         Try updating to a specific version\n",
        )
    else:
        idx = sorted(versions).index(ver) if ver in versions else 0
        if idx + 1 == len(versions):
            print("The version you have checked out is the latest version\n")
        else:
            print(
                "Newest version |{}| type:\n\npython update.py {}\n".format(
                    sorted(versions)[-1], sorted(versions)[-1]
                )
            )
    print("--")


def ask_user_input(ver="#.#.#", responses=["y", "n"]):
    msg = f"Do you want to update to {ver}?"
    use_msg = msg.format(ver) + f" ([{responses[0]}], {responses[1]}): "
    response = input(use_msg) or "y"
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


# THIS guy!!!
def _update(branch=None, version=None):
    info()
    ver = branch or version
    resp = ask_user_input(ver=ver)
    if resp == "y":
        if branch:
            git.checkout_branch(branch)
        elif version:
            git.checkout_version(version)
        elif branch is None and version is None:
            git.checkout_version(sorted(ALL_VERSIONS)[-1])
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
        git.checkout_single_file(file="iblrig/_update.py", branch="master")

    if args.update and args.b:
        if args.b not in ALL_BRANCHES:
            print("Not found:", args.b)
            return
        git.checkout_single_file(file="_update.py", branch=args.b)

    if args.b and args.b in ALL_BRANCHES:
        _update(branch=args.b)
    elif args.b and args.b not in ALL_BRANCHES:
        print("Branch", args.b, "not found")

    if args.v and args.v in ALL_VERSIONS:
        _update(version=args.v)
    elif args.v and args.v not in ALL_VERSIONS:
        print("Version", args.v, "not found")

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


if __name__ == "__main__":
    pass
