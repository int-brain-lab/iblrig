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
REQUIREMENTS_FILE = IBLRIG_ROOT_PATH / 'requirements.txt'
# PYBPOD_PATH = os.path.join(IBLRIG_ROOT_PATH, 'pybpod')


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


def check_dependencies(conda):
    # Check if Git and conda are installed
    print('\n\nINFO: Checking for dependencies:')
    print("N" * 79)
    try:
        subprocess.check_output(["git", "--version"])
        print("Git... OK")
        subprocess.check_output([conda, "update", "-y", "-n", "base",
                                 "-c", "defaults", "conda"])
        print("Conda... OK")
    except Exception as err:
        print(err, "\nEither git or conda were not found on your system\n")
        return
    print("N" * 79)
    print("All dependencies OK.")


def install_environment(conda):
    print('\n\nINFO: Installing iblenv:')
    print("N" * 79)
    # Checks id env is already installed
    env = get_iblenv(conda)
    # Creates commands
    create_command = '{} create -n iblenv'. format(conda).split()
    remove_command = '{} env remove -n iblenv'. format(conda).split()
    # Installes the env
    if env:
        print("Found pre-existing environment in {}".format(env),
              "\nDo you want to reinstall the environment? (y/n):")
        user_input = input()
        if user_input == 'y':
            subprocess.call(remove_command)
            subprocess.call(create_command)
        elif user_input != 'n' and user_input != 'y':
            print("Please answer 'y' or 'n'")
            install_environment()
        elif user_input == 'n':
            pass
    else:
        subprocess.call(create_command)

    print("N" * 79)
    print("iblenv installed.")


def get_iblenv(conda):
    # Find ibllib environment
    all_envs = subprocess.check_output([conda, "env", "list", "--json"])
    all_envs = json.loads(all_envs.decode('utf-8'))
    pat = re.compile("^.+iblenv$")
    iblenv = [x for x in all_envs['envs'] if pat.match(x)]
    iblenv = iblenv[0] if iblenv else None
    return iblenv


def get_iblenv_pip_n_python(conda):
    iblenv = get_iblenv(conda)
    if sys.platform in ['Windows', 'windows', 'win32']:
        pip = os.path.join(iblenv, 'Scripts', 'pip.exe')
        python = os.path.join(iblenv, "python.exe")
    elif sys.platform in ['Linux', 'linux']:
        pip = os.path.join(iblenv, "bin", "pip")
        python = os.path.join(iblenv, "bin", "python")
    elif sys.platform in ['Darwin', 'macOSx', 'osx']:
        print("ERROR: macOSx is not supported yet\nInstallation aborted!")
    else:
        print('\nERROR: Unsupported OS\nInstallation aborted!')

    return pip, python


# def check_pybpod_for_initialization():
#     print('\n\nINFO: Checking pybpod for initialization:')
#     print("N" * 79)
#     os.chdir(IBLRIG_ROOT_PATH)
#     if not os.listdir(PYBPOD_PATH):
#         subprocess.call(["git", "submodule", "update", "--init",
#                          "--recursive"])
#     print("N" * 79)
#     print("PyBpod initialized.")


def install_iblrig_requirements():
    print('\n\nINFO: Installing IBL specific dependencies:')
    print("N" * 79)
    if iblenv is None:
        msg = "Can't install extra dependencies, pybpod-environment not found"
        raise ValueError(msg)
    # Define site-packages folder
    install_to = os.path.join(iblenv, SITE_PACKAGES)

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


def clone_ibllib():
    print('\n\nINFO: Cloning ibllib:')
    print("N" * 79)
    os.chdir(str(IBLRIG_ROOT_PATH.parent))
    subprocess.call(["git", "clone",
                     'https://github.com/int-brain-lab/ibllib.git'])
    os.chdir(IBLRIG_ROOT_PATH)
    print("N" * 79)
    print("ibllib cloned.")


# def install_ibllib():
#     print('\n\nINFO: Installing ibllib:')
#     print("N" * 79)
#     if iblenv is None:
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
    iblenv = get_iblenv(CONDA)

    # try:
    #     check_dependencies()
    #     check_pybpod_for_initialization()
    #     clone_water_calibration_plugin()
    #     install_environment()
    #     print("\n\n")
    #     iblenv, PIP, PYTHON_FILE, PYTHON = get_env_constants()
    #     subprocess.call([PYTHON, '-m', 'pip', 'install', '--upgrade', 'pip'])
    #     install_extra_deps()
    #     install_water_calibration_plugin()
    #     # install_pybpod()
    #     conf_pybpod_settings()
    #     print("\nIts time to install Bonsai:\n  Please install all packages.",
    #           "\nIMPORTANT: the Bonsai.Bpod package is in the pre-release tab.")
    #     install_bonsai()
    #     print("Almost done...\nPlease run the following command:\n",
    #           r"    activate pybpod-environment && cd pybpod", "\n",
    #           r"    python utils\install.py")
    # except IOError as msg:
    #     print(msg, "\n\nSOMETHING IS WRONG: Bad! Bad install file!")


