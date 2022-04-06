#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date:   2018-06-08 11:04:05
# @Editor: Michele Fabbri
# @Edit_Date: 2022-01-28
import os
import shutil
import subprocess
import sys
from pathlib import Path

from setup_pybpod import main as setup_pybpod

import iblrig.envs as envs
import iblrig.git as git


IBLRIG_ROOT_PATH = Path.cwd()
git.fetch()
ALL_BRANCHES = git.get_branches()
ALL_VERSIONS = git.get_versions()
BRANCH = git.get_current_branch()
VERSION = git.get_current_version()


def check_reinstall_required():
    REINSTALL = True if list(Path(IBLRIG_ROOT_PATH).glob("reinstall")) else False
    if REINSTALL:
        print("\nPlease deactivate iblrig and reinstall from the base environment")
        print("\n-------------------------------------")
        print("\nconda deactivate && python install.py")
        print("\n-------------------------------------\n")

        raise SystemError("This rig version needs to be reinstalled from base environment\n")


def iblrig_params_path():
    return str(Path(os.getcwd()).parent / "iblrig_params")


def update_rig_env():
    print("\nUpdating iblrig")
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
    pip = envs.get_env_pip("ibllib")
    os.system("pip install ibllib -U")
    os.system(f"{pip} install ibllib -U")


def update_bonsai_config():
    if sys.platform not in ["Windows", "windows", "win32"]:
        print("Skipping Bonsai installation on non-Windows platforms")
        return
    print("\nUpdating Bonsai")
    broot = IBLRIG_ROOT_PATH / "Bonsai"
    bonsai_exe = broot / "Bonsai64.exe"
    if bonsai_exe.exists():
        subprocess.call([str(bonsai_exe), '--no-editor', str(broot / 'empty.bonsai')])
    else:
        bonsai_exe = broot / "Bonsai.exe"
        subprocess.call([str(bonsai_exe), "--no-editor"])
    print("Done")


def remove_bonsai():
    if sys.platform not in ["Windows", "windows", "win32"]:
        print("Skipping Bonsai installation on non-Windows platforms")
        return
    broot = IBLRIG_ROOT_PATH / "Bonsai"
    shutil.rmtree(broot)


def upgrade_bonsai(version, branch):
    print("\nUpgrading Bonsai")
    if sys.platform not in ["Windows", "windows", "win32"]:
        print("Skipping Bonsai installation on non-Windows platforms")
        return
    remove_bonsai()
    if not version:
        git.checkout_branch(branch)
    elif not branch:
        git.checkout_version(version)
    here = os.getcwd()
    os.chdir(os.path.join(IBLRIG_ROOT_PATH, "Bonsai"))
    broot = IBLRIG_ROOT_PATH / "Bonsai"
    bonsai_exe = broot / "Bonsai64.exe"
    if bonsai_exe.exists():
        subprocess.call([str(bonsai_exe), '--no-editor', str(broot / 'empty.bonsai')])
    else:
        subprocess.call("setup.bat")
    os.chdir(here)


def check_update_exists():
    idx = sorted(ALL_VERSIONS).index(VERSION) if VERSION in ALL_VERSIONS else 0
    if idx + 1 == len(ALL_VERSIONS):
        print("The version you have checked out is the latest version\n")
        return False
    else:
        print(
            "Newer version available |{}| type:\n\npython update.py -v {}\n".format(
                sorted(ALL_VERSIONS)[-1], sorted(ALL_VERSIONS)[-1]
            )
        )
        return True


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
    if not ver:
        print(
            "\nWARNING: You appear to be on an untagged commit.",
            "\n         Try updating to a specific version\n",
        )
    else:
        check_update_exists()
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


# THIS guy!!!return
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

        check_reinstall_required()  # Will raise error if reinstall file exists

        update_pip()
        update_rig_env()
        setup_pybpod(iblrig_params_path())
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

    # TODO: remove once functionality implemented natively
    if args.ibllib:
        update_ibllib()

    if args.info:
        info()

    if args.setup_pybpod:
        setup_pybpod(iblrig_params_path())

    if args.iblrig:
        update_rig_env()

    if args.pip:
        update_pip()

    if args.conda:
        update_conda()

    if args.upgrade_bonsai:
        upgrade_bonsai(VERSION, BRANCH)
        update_bonsai_config()

    if args.update_exists:
        check_update_exists()

    return


if __name__ == "__main__":
    pass
