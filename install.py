#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from packaging import version

# BEGIN CONSTANT DEFINITION
IBLRIG_ROOT_PATH = Path.cwd()

if sys.platform not in ["Windows", "windows", "win32"]:
    print("\nERROR: Unsupported OS\nInstallation might not work!")
# END CONSTANT DEFINITION


def get_iblenv():
    # Find ibllib environment
    all_envs = subprocess.check_output(["conda", "env", "list", "--json"])
    all_envs = json.loads(all_envs.decode("utf-8"))
    pat = re.compile("^.+iblenv$")
    iblenv = [x for x in all_envs["envs"] if pat.match(x)]
    iblenv = iblenv[0] if iblenv else None
    return iblenv


def get_iblenv_python(rpip=False):
    iblenv = get_iblenv()
    pip = os.path.join(iblenv, "Scripts", "pip.exe")
    python = os.path.join(iblenv, "python.exe")

    return python if not rpip else pip


def check_dependencies():
    # Check if Git and conda are installed
    print("\n\nINFO: Checking for dependencies:")
    print("N" * 79)
    try:
        os.system("conda -V")
        conda_version = str(subprocess.check_output(["conda", "-V"])).split(" ")[1].split("\\n")[0]
        if version.parse(conda_version) < version.parse("4.9"):
            print("Trying to update conda")
            # os.system("conda update -y -n base -c defaults conda")
            subprocess.check_output(
                ["conda", "update", "-y", "-n", "base", "-c", "defaults", "conda"]
            )
            return check_dependencies()
        print("conda... OK")
    except BaseException as e:
        print(e)
        print("Not found: conda, aborting install...")
        return 1

    try:
        python_version = (
            str(subprocess.check_output(["python", "-V"])).split(" ")[1].split("\\n")[0]
        )
        if version.parse(python_version) < version.parse("3.8"):
            print("Trying to update python base version...")
            os.systm("conda update python")
            raise ValueError
        print("python... OK")
    except BaseException as e:
        print(e)
        print("Not found: python, aborting install...")
        return 1

    try:
        os.system("pip -V")
        pip_version = str(subprocess.check_output(["pip", "-V"])).split(" ")[1]
        if not version.parse(pip_version) >= version.parse("20.0.0"):
            print("Trying to upgrade pip...")
            os.system("python -m pip install --upgrade pip")
            return check_dependencies()
        print("pip... OK")
    except BaseException as e:
        print(e)
        print("Not found: pip, aborting install...")
        return 1

    try:
        subprocess.check_output(["git", "--version"])
        os.system("git --version")
        git_version = (
            str(subprocess.check_output(["git", "--version"])).split(" ")[2].strip("\\n'")
        )
        if version.parse(git_version) < version.parse("2.25"):
            if sys.platform in ["Windows", "windows", "win32"]:
                os.system("git update-git-for-windows -y")
            elif sys.platform in ["linux", "unix"]:
                print("Please update git using your package manager")
                return 1
            return check_dependencies()
        print("git... OK")
    except BaseException as e:
        print(e)
        print("Not found: git")
        print("Trying to install git...")
        os.system("conda -y install git")
        return check_dependencies()

    print("N" * 79)
    print("All dependencies OK.")
    return 0


def install_environment():
    print("\n\nINFO: Installing iblenv:")
    print("N" * 79)
    # Checks id env is already installed
    env = get_iblenv()
    # Creates commands
    create_command = "conda create -y -n iblenv python=3.7"
    remove_command = "conda env remove -y -n iblenv"
    # Installes the env
    if env:
        print(
            "Found pre-existing environment in {}".format(env),
            "\nDo you want to reinstall the environment? (y/n):",
        )
        user_input = input()
        if user_input == "y":
            os.system(remove_command)
            return install_environment()
        elif user_input != "n" and user_input != "y":
            print("Please answer 'y' or 'n'")
            return install_environment()
        elif user_input == "n":
            return
    else:
        os.system(create_command)

    print("N" * 79)
    print("iblenv installed.")
    return 0


def install_deps():
    os.system("conda activate iblenv && pip install -r requirements.txt -U")
    os.system("conda activate iblenv && pip install -e .")


def install_iblrig_requirements():
    print("\n\nINFO: Installing IBLrig requirements:")
    print("N" * 79)
    print("N" * 39, "Installing git")
    os.system("conda install -y -n iblenv git")
    print("N" * 39, "Installing scipy")
    os.system("conda install -y -n iblenv scipy")
    print("N" * 39, "Installing requests")
    os.system("conda install -y -n iblenv requests")

    print("N" * 39, "(pip) Installing python-osc")
    os.system("conda activate iblenv && pip install python-osc")
    os.system("conda activate iblenv && pip install cython")
    print("N" * 39, "(pip) Installing sounddevice")
    os.system("conda activate iblenv && pip install sounddevice")
    print("N" * 39, "(pip) Installing PyBpod")
    os.system("conda activate iblenv && pip install pybpod -U")
    # os.system("conda activate iblenv && pip install --upgrade --force-reinstall pybpod")  # noqa
    # os.system("activate iblenv && pip install -U pybpod")
    print("N" * 39, "(pip) Installing PyQtWebEngine")
    os.system("conda activate iblenv && pip install PyQtWebEngine")
    print("N" * 39, "(pip) Installing PyBpod Alyx plugin")
    os.system("conda activate iblenv && pip install --upgrade pybpod-gui-plugin-alyx")  # noqa
    print("N" * 39, "(pip) Installing PyBpod Soundcard plugin")
    os.system("conda activate iblenv && pip install --upgrade pybpod-gui-plugin-soundcard")  # noqa
    print("N" * 39, "(pip) Installing iblrig")
    os.system("conda activate iblenv && pip install -e .")
    print("N" * 79)
    print("IBLrig requirements installed.")


def configure_iblrig_params():
    print("\n\nINFO: Setting up default project config in ../iblrig_params:")
    print("N" * 79)
    iblenv = get_iblenv()
    if iblenv is None:
        msg = "Can't configure iblrig_params, iblenv not found"
        raise ValueError(msg)
    python = get_iblenv_python()
    iblrig_params_path = IBLRIG_ROOT_PATH.parent / "iblrig_params"
    if iblrig_params_path.exists():
        print(
            f"Found previous configuration in {str(iblrig_params_path)}",
            "\nDo you want to reset to default config? (y/n)",
        )
        user_input = input()
        if user_input == "n":
            return
        elif user_input == "y":
            subprocess.call([python, "setup_default_config.py", str(iblrig_params_path)])
        elif user_input != "n" and user_input != "y":
            print("\n Please select either y of n")
            return configure_iblrig_params()
    else:
        iblrig_params_path.mkdir(parents=True, exist_ok=True)
        subprocess.call([python, "setup_default_config.py", str(iblrig_params_path)])


def install_bonsai():
    print("\n\nDo you want to install Bonsai now? (y/n):")
    user_input = input()
    if user_input == "y":
        subprocess.call(os.path.join(IBLRIG_ROOT_PATH, "Bonsai", "Bonsai64.exe"))
    elif user_input != "n" and user_input != "y":
        print("Please answer 'y' or 'n'")
        return install_bonsai()
    elif user_input == "n":
        return


if __name__ == "__main__":
    ALLOWED_ACTIONS = ["new"]
    parser = argparse.ArgumentParser(description="Install iblrig")
    parser.add_argument(
        "--new",
        required=False,
        default=False,
        action="store_true",
        help="Use new install procedure",
    )
    args = parser.parse_args()

    try:
        check_dependencies()
        install_environment()
        if args.new:
            install_deps()
        elif not args.new:
            install_iblrig_requirements()

        configure_iblrig_params()
        print("\nIts time to install Bonsai:")
        install_bonsai()
        print("\n\nINFO: iblrig installed, you should be good to go!")
    except IOError as msg:
        print(msg, "\n\nSOMETHING IS WRONG: Bad! Bad install file!")

    print(".")
