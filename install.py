#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-07-12 13:08:10
import os
import shutil
import json
import subprocess
import re
import sys
from pathlib import Path

# Constants assuming Windows
IBLRIG_ROOT_PATH = Path.cwd()
ENV_FILE = IBLRIG_ROOT_PATH / 'requirements.txt'
# PYBPOD_PATH = os.path.join(IBLRIG_ROOT_PATH, 'pybpod')


# def get_pybpod_env(conda):
#     # Find environment
#     ENVS = subprocess.check_output([conda, "env", "list", "--json"])
#     ENVS = json.loads(ENVS.decode('utf-8'))
#     pat = re.compile("^.+pybpod-environment$")
#     PYBPOD_ENV = [x for x in ENVS['envs'] if pat.match(x)]
#     PYBPOD_ENV = PYBPOD_ENV[0] if PYBPOD_ENV else None
#     return PYBPOD_ENV


# BASE_ENV_FILE = 'environment-{}.yml'
if sys.platform in ['Windows', 'windows', 'win32']:
    CONDA = "conda"
    SITE_PACKAGES = os.path.join("lib", "site-packages")
elif sys.platform in ['Linux', 'linux']:
    p = sys.prefix.split(os.sep)
    p = [x for x in p if 'env' not in x]
    conda_path = '{}'.format(os.sep).join(p)
    CONDA = os.path.join(conda_path, "bin", "conda")
    SITE_PACKAGES = os.path.join("lib", "python3.6", "site-packages")
elif sys.platform in ['Darwin', 'macOSx', 'osx']:
    print("ERROR: macOSx is not supported yet\nInstallation aborted!")
else:
    print('\nERROR: Unsupported OS\nInstallation aborted!')


def get_env_constants():
    if sys.platform in ['Windows', 'windows', 'win32']:
        PYBPOD_ENV = get_pybpod_env(CONDA)
        PIP = os.path.join(PYBPOD_ENV, 'Scripts', 'pip.exe')
        PYTHON_FILE = "python.exe"
    elif sys.platform in ['Linux', 'linux']:
        PYBPOD_ENV = get_pybpod_env(CONDA)
        PIP = os.path.join(sys.prefix, "bin", "pip")
        PYTHON_FILE = os.path.join("bin", "python")
    elif sys.platform in ['Darwin', 'macOSx', 'osx']:
        print("ERROR: macOSx is not supported yet\nInstallation aborted!")
    else:
        print('\nERROR: Unsupported OS\nInstallation aborted!')

    PYTHON = os.path.join(PYBPOD_ENV, PYTHON_FILE)

    return PYBPOD_ENV, PIP, PYTHON_FILE, PYTHON


def check_dependencies():
    # Check if Git and conda are installed
    print('\n\nINFO: Checking for dependencies:')
    print("N" * 79)
    try:
        subprocess.check_output(["git", "--version"])
        print("Git... OK")
        subprocess.check_output([CONDA, "update", "-y", "-n", "base",
                                 "-c", "defaults", "conda"])
        print("Conda... OK")
    except Exception as err:
        print(err, "\nEither git or conda were not found on your system\n")
        return
    print("N" * 79)
    print("All dependencies OK.")


# def check_pybpod_for_initialization():
#     print('\n\nINFO: Checking pybpod for initialization:')
#     print("N" * 79)
#     os.chdir(IBLRIG_ROOT_PATH)
#     if not os.listdir(PYBPOD_PATH):
#         subprocess.call(["git", "submodule", "update", "--init",
#                          "--recursive"])
#     print("N" * 79)
#     print("PyBpod initialized.")


# def clone_water_calibration_plugin():
#     print('\n\nINFO: Cloning water-claibration-plugin:')
#     print("N" * 79)
#     os.chdir(os.path.join(PYBPOD_PATH, 'plugins'))
#     subprocess.call(["git", "clone",
#                      'https://bitbucket.org/azi92rach/water-calibration-plugin.git'])
#     os.chdir(IBLRIG_ROOT_PATH)
#     print("N" * 79)
#     print("PyBpod initialized and water-calibration-plugin cloned.")


def install_environment():
    print('\n\nINFO: Installing pybpod-environment:')
    print("N" * 79)
    # Install pybpod-environment
    env = get_pybpod_env(CONDA)
    command = '{} env create -f {}'. format(CONDA, os.path.join(
        PYBPOD_PATH, 'utils', ENV_FILE)).split()
    force_command = '{} env create -f {} --force'. format(CONDA, os.path.join(
        PYBPOD_PATH, 'utils', ENV_FILE)).split()
    if env:
        print("Found pre-existing environment in {}".format(env),
              "\nDo you want to reinstall the environment? (y/n):")
        user_input = input()
        if user_input == 'y':
            subprocess.call(force_command)
        elif user_input != 'n' and user_input != 'y':
            print("Please answer 'y' or 'n'")
            install_environment()
        elif user_input == 'n':
            pass
    else:
        subprocess.call(command)

    print("N" * 79)
    print("pybpod-environment installed.")


def install_extra_deps():
    print('\n\nINFO: Installing IBL specific dependencies:')
    print("N" * 79)
    if PYBPOD_ENV is None:
        msg = "Can't install extra dependencies, pybpod-environment not found"
        raise ValueError(msg)
    # Define site-packages folder
    install_to = os.path.join(PYBPOD_ENV, SITE_PACKAGES)

    print("N" * 39, 'Installing sounddevice')
    subprocess.call([CONDA, "install", "-y", "-n", "pybpod-environment",
                     "-c", "conda-forge", "python-sounddevice"])
    print("N" * 39, 'Installing requests')
    subprocess.call([CONDA, "install", "-y", "-n",
                     "pybpod-environment", "requests"])
    print("N" * 39, 'Installing requests dependencies')
    subprocess.call([CONDA, "install", "-y",
                     "-n", "pybpod-environment", "requests", "--update-deps"])
    # Install extra depencencies using pip
    print("N" * 39, '(pip) Installing python-osc')
    subprocess.call([PIP, "install", "--target={}".format(install_to),
                     "python-osc"])
    print("N" * 79)
    print("IBL specific dependencies installed.")


# def install_pybpod():
#     print('\n\nINFO: Installing pybpod:')
#     print("N" * 79)
#     if PYBPOD_ENV is None:
#         msg = "Can't install pybpod, pybpod-environment not found"
#         raise ValueError(msg)
#     # Install pybpod
#     os.chdir(PYBPOD_PATH)
#     subprocess.call([PYTHON, "utils/install.py"])
#     os.chdir(IBLRIG_ROOT_PATH)
#     print("N" * 79)
#     print("INFO: PyBpod installed.")


# def install_water_calibration_plugin():
#     print('\n\nINFO: Installing water-calibration-plugins:')
#     print("N" * 79)
#     os.chdir(os.path.join(PYBPOD_PATH, 'plugins'))
#     subprocess.call([PIP, "install", "-e", "water-calibration-plugin"])
#     os.chdir(PYBPOD_PATH)
#     print("N" * 79)
#     print("water-calibration-plugin installed.")


# def conf_pybpod_settings():
#     print('\n\nINFO: Configuring pybpod IBL project:')
#     print("N" * 79)
#     # Copy user settings
#     src = os.path.join(IBLRIG_ROOT_PATH, 'user_settings.py')
#     shutil.copy(src, PYBPOD_PATH)
#     print("N" * 79)
#     print("Configuration complete.")


def install_bonsai():
    print("\n\nDo you want to install Bonsai now? (y/n):")
    user_input = input()
    if user_input == 'y':
        subprocess.call(os.path.join(IBLRIG_ROOT_PATH,
                                     'Bonsai-2.3', 'Bonsai64.exe'))
    elif user_input != 'n' and user_input != 'y':
        print("Please answer 'y' or 'n'")
        install_bonsai()
    elif user_input == 'n':
        pass


if __name__ == '__main__':
    try:
        check_dependencies()
        # check_pybpod_for_initialization()
        # clone_water_calibration_plugin()
        install_environment()
        print("\n\n")
        PYBPOD_ENV, PIP, PYTHON_FILE, PYTHON = get_env_constants()
        subprocess.call([PYTHON, '-m', 'pip', 'install', '--upgrade', 'pip'])
        install_extra_deps()
        install_water_calibration_plugin()
        # install_pybpod()
        conf_pybpod_settings()
        print("\nIts time to install Bonsai:\n  Please install all packages.",
              "\nIMPORTANT: the Bonsai.Bpod package is in the pre-release tab.")
        install_bonsai()
        print("Almost done...\nPlease run the following command:\n",
              r"    activate pybpod-environment && cd pybpod", "\n",
              r"    python utils\install.py")
    except IOError as msg:
        print(msg, "\n\nSOMETHING IS WRONG: Bad! Bad install file!")


