#!/usr/bin/env python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import argparse


# BEGIN CONSTANT DEFINITION
IBLRIG_ROOT_PATH = Path.cwd()

if sys.platform not in ['Windows', 'windows', 'win32']:
    print('\nERROR: Unsupported OS\nInstallation might not work!')
# END CONSTANT DEFINITION


def get_iblenv():
    # Find ibllib environment
    all_envs = subprocess.check_output(["conda", "env", "list", "--json"])
    all_envs = json.loads(all_envs.decode('utf-8'))
    pat = re.compile("^.+iblenv$")
    iblenv = [x for x in all_envs['envs'] if pat.match(x)]
    iblenv = iblenv[0] if iblenv else None
    return iblenv


def get_iblenv_python(rpip=False):
    iblenv = get_iblenv()
    pip = os.path.join(iblenv, 'Scripts', 'pip.exe')
    python = os.path.join(iblenv, "python.exe")

    return python if not rpip else pip


def check_dependencies():
    # Check if Git and conda are installed
    print('\n\nINFO: Checking for dependencies:')
    print("N" * 79)
    try:
        subprocess.check_output(["git", "--version"])
        os.system("git --version")
        print("git... OK")
        # os.system("conda update -y -n base -c defaults conda")
        os.system("conda -V")
        print("conda... OK")
        # os.system("python -m pip install --upgrade pip")
        os.system("pip -V")
        print("pip... OK")
    except Exception as err:
        print(err, "\nEither git, conda, or pip were not found.\n")
        return
    print("N" * 79)
    print("All dependencies OK.")


def install_environment():
    print('\n\nINFO: Installing iblenv:')
    print("N" * 79)
    # Checks id env is already installed
    env = get_iblenv()
    # Creates commands
    create_command = 'conda create -y -n iblenv python=3.7'
    remove_command = 'conda env remove -y -n iblenv'
    # Installes the env
    if env:
        print("Found pre-existing environment in {}".format(env),
              "\nDo you want to reinstall the environment? (y/n):")
        user_input = input()
        if user_input == 'y':
            os.system(remove_command)
            return install_environment()
        elif user_input != 'n' and user_input != 'y':
            print("Please answer 'y' or 'n'")
            return install_environment()
        elif user_input == 'n':
            return
    else:
        os.system(create_command)
        os.system("conda activate iblenv && python -m pip install --upgrade pip")  # noqa
    print("N" * 79)
    print("iblenv installed.")


def install_deps():
    os.system("conda activate iblenv && pip install -r requirements.txt")


def install_iblrig_requirements():
    print('\n\nINFO: Installing IBLrig requirements:')
    print("N" * 79)
    print("N" * 39, 'Installing git')
    os.system("conda install -y -n iblenv git")
    print("N" * 39, 'Installing scipy')
    os.system("conda install -y -n iblenv scipy")
    print("N" * 39, 'Installing requests')
    os.system("conda install -y -n iblenv requests")

    print("N" * 39, '(pip) Installing python-osc')
    os.system("conda activate iblenv && pip install python-osc")
    os.system("conda activate iblenv && pip install cython")
    print("N" * 39, '(pip) Installing sounddevice')
    os.system("conda activate iblenv && pip install sounddevice")
    print("N" * 39, '(pip) Installing PyBpod')
    os.system("conda activate iblenv && pip install pybpod -U")
    # os.system("conda activate iblenv && pip install --upgrade --force-reinstall pybpod")  # noqa
    # os.system("activate iblenv && pip install -U pybpod")
    print("N" * 39, '(pip) Installing PyQtWebEngine')
    os.system("conda activate iblenv && pip install PyQtWebEngine")
    print("N" * 39, '(pip) Installing PyBpod Alyx plugin')
    os.system(
        "conda activate iblenv && pip install --upgrade pybpod-gui-plugin-alyx")  # noqa
    print("N" * 39, '(pip) Installing PyBpod Soundcard plugin')
    os.system(
        "conda activate iblenv && pip install --upgrade pybpod-gui-plugin-soundcard")  # noqa
    print("N" * 79)
    print("IBLrig requirements installed.")


def clone_ibllib():
    print('\n\nINFO: Cloning ibllib:')
    print("N" * 79)
    os.chdir(IBLRIG_ROOT_PATH.parent)
    ibllib_path = IBLRIG_ROOT_PATH.parent / 'ibllib'
    if ibllib_path.exists():
        print("ibllib folder is already present.",
              "\nDo you want to reinstall? (y/n)")
        user_input = input()
        if user_input == 'n':
            return user_input
        elif user_input == 'y':
            try:
                os.system(f"rd /s /q {ibllib_path}")
                return clone_ibllib()
            except:  # noqa
                print("\nCould not delete ibllib folder",
                      "\nPlease delete it manually and retry.")
                return clone_ibllib()
        elif user_input != 'n' and user_input != 'y':
            print("\n Please select either y of n")
            return clone_ibllib()
    else:
        subprocess.call(["git", "clone",
                         'https://github.com/int-brain-lab/ibllib.git'])

    os.chdir(IBLRIG_ROOT_PATH)
    print("N" * 79)
    print("ibllib cloned.")


def install_ibllib(user_input=False):
    if user_input == 'n':
        return

    print('\n\nINFO: Installing ibllib:')
    print("N" * 79)
    os.chdir(IBLRIG_ROOT_PATH.parent / 'ibllib/python')
    os.system("conda activate iblenv && pip install -e .")
    os.chdir(IBLRIG_ROOT_PATH)
    print("N" * 79)
    print("INFO: ibllib installed.")


def configure_iblrig_params():
    print('\n\nINFO: Setting up default project config in ../iblrig_params:')
    print("N" * 79)
    iblenv = get_iblenv()
    if iblenv is None:
        msg = "Can't configure iblrig_params, iblenv not found"
        raise ValueError(msg)
    python = get_iblenv_python()
    iblrig_params_path = IBLRIG_ROOT_PATH.parent / 'iblrig_params'
    if iblrig_params_path.exists():
        print(f"Found previous configuration in {str(iblrig_params_path)}",
              "\nDo you want to reset to default config? (y/n)")
        user_input = input()
        if user_input == 'n':
            return
        elif user_input == 'y':
            subprocess.call([python, "setup_default_config.py",
                             str(iblrig_params_path)])
        elif user_input != 'n' and user_input != 'y':
            print("\n Please select either y of n")
            return configure_iblrig_params()
    else:
        subprocess.call([python, "setup_default_config.py",
                         str(iblrig_params_path)])


def install_bonsai():
    print("\n\nDo you want to install Bonsai now? (y/n):")
    user_input = input()
    if user_input == 'y':
        subprocess.call(os.path.join(IBLRIG_ROOT_PATH,
                                     'Bonsai-2.3', 'Bonsai64.exe'))
    elif user_input != 'n' and user_input != 'y':
        print("Please answer 'y' or 'n'")
        return install_bonsai()
    elif user_input == 'n':
        return


if __name__ == '__main__':
    ALLOWED_ACTIONS = ['new']
    parser = argparse.ArgumentParser(description='Install iblrig')
    parser.add_argument('--new', required=False, default=False,
                        action='store_true', help='Use new install procedure')
    args = parser.parse_args()

    try:
        check_dependencies()
        install_environment()
        if args.new:
            install_deps()
        elif not args.new:
            install_iblrig_requirements()
            yn = clone_ibllib()
            install_ibllib(user_input=yn)

        configure_iblrig_params()
        print("\nIts time to install Bonsai:")
        install_bonsai()
        print("\n\nINFO: iblrig installed, you should be good to go!")
    except IOError as msg:
        print(msg, "\n\nSOMETHING IS WRONG: Bad! Bad install file!")

    print(".")
