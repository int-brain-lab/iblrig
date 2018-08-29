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

# Constants assuming Windows
IBLRIG_ROOT_PATH = os.getcwd()
PYBPOD_PATH = os.path.join(IBLRIG_ROOT_PATH, 'pybpod')
SUBMODULES_FOLDERS = [
    'pybpod',
    'water-calibration-plugin',
]
PYBPOD_SUBMODULES_FOLDERS = [
    'pybpod-alyx-module',
    'pybpod-gui-plugin-trial-timeline',
    'pybpod-gui-plugin-waveplayer',
    'logging-bootstrap',
    'pyforms',
    'pyforms-generic-editor',
    'pybpod-api',
    'pybpod-gui-api',
    'pybpod-gui-plugin',
    'pybpod-gui-plugin-session-history',
    'pybpod-gui-plugin-timeline',
    'pybpod-rotary-encoder-module',
    'safe-collaborative-architecture',
    'pge-plugin-terminal'
]


def get_pybpod_env(conda):
    # Find environment
    ENVS = subprocess.check_output([conda, "env", "list", "--json"])
    ENVS = json.loads(ENVS.decode('utf-8'))
    pat = re.compile("^.+pybpod-environment$")
    PYBPOD_ENV = [x for x in ENVS['envs'] if pat.match(x)]
    PYBPOD_ENV = PYBPOD_ENV[0] if PYBPOD_ENV else None
    return PYBPOD_ENV


def get_bonsai_path():
    from pathlib import Path
    BONSAI = Path.home() / "AppData/Local/Bonsai/Bonsai64.exe"
    if BONSAI.exists():
        return str(BONSAI)
    else:
        return None

BONSAI = get_bonsai_path()
BASE_ENV_FILE = 'environment-{}.yml'

if sys.platform in ['Windows', 'windows', 'win32']:
    ENV_FILE = BASE_ENV_FILE.format('windows-10')
    CONDA = "conda"
    SITE_PACKAGES = os.path.join("lib", "site-packages")
elif sys.platform in ['Linux', 'linux']:
    ENV_FILE = BASE_ENV_FILE.format('ubuntu-17.10')
    p = sys.prefix.split(os.sep)
    p = [x for x in p if 'env' not in x]
    conda_path = '{}'.format(os.sep).join(p)
    CONDA = os.path.join(conda_path, "bin", "conda")
    SITE_PACKAGES = os.path.join("lib", "python3.6", "site-packages")
elif sys.platform in ['Darwin', 'macOSx', 'osx']:
    ENV_FILE = BASE_ENV_FILE.format('macOSx')
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
        subprocess.check_output([CONDA])
        print("Conda... OK")
    except Exception as err:
        print(err, "\nEither git or conda were not found on your system\n")
        return
    # Check if Bonsai is installed
    if BONSAI is None:
        print("WARNING: Bonsai not found, task will run with no visual stim.")
        print("Installation will proceed...")
    else:
        print("Bonsai... OK")
    print("N" * 79)
    print("All dependencies OK.")


def check_submodules():
    print('\n\nINFO: Checking submodules for initialization:')
    print("N" * 79)
    os.chdir(IBLRIG_ROOT_PATH)
    for submodule in SUBMODULES_FOLDERS:
        if not os.listdir(os.path.join(IBLRIG_ROOT_PATH, submodule)):
            subprocess.call(["git", "submodule", "update", "--init",
                             "--recursive"])
    print("N" * 79)
    print("All submodules OK.")


def install_environment():
    print('\n\nINFO: Installing pybpod-environment:')
    print("N" * 79)
    # Install pybpod-environment
    command = '{} env create -f {}'. format(CONDA, os.path.join(
        PYBPOD_PATH, ENV_FILE)).split()

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

    # Install extra depencencies using conda
    print("N" * 39, 'Installing scipy...')
    subprocess.call([CONDA, "install", "-y", "-n",
                     "pybpod-environment", "scipy"])
    print("N" * 39, 'Installing pandas')
    subprocess.call([CONDA, "install", "-y", "-n",
                     "pybpod-environment", "pandas"])
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


def install_pybpod():
    print('\n\nINFO: Installing pybpod:')
    print("N" * 79)
    if PYBPOD_ENV is None:
        msg = "Can't install pybpod, pybpod-environment not found"
        raise ValueError(msg)
    # Install pybpod
    os.chdir(PYBPOD_PATH)
    subprocess.call([PYTHON, "install.py"])
    os.chdir('..')
    print("N" * 79)
    print("INFO: PyBpod installed.")


def install_pybpod_modules():
    print('\n\nINFO: Installing pybpod modules and plugins:')
    print("N" * 79)
    subprocess.call([PIP, "install", "-e", "water-calibration-plugin"])
    os.chdir(PYBPOD_PATH)
    for submodule in PYBPOD_SUBMODULES_FOLDERS:
        subprocess.call([PIP, "install", "-e", submodule])
    os.chdir('..')
    print("N" * 79)
    print("PyBpod modules and plugins installed.")


def conf_pybpod_settings():
    print('\n\nINFO: Configuring pybpod IBL project:')
    print("N" * 79)
    # Copy user settings
    src = os.path.join(IBLRIG_ROOT_PATH, 'user_settings.py')
    shutil.copy(src, PYBPOD_PATH)
    print("N" * 79)
    print("Configuration complete.")


if __name__ == '__main__':
    check_dependencies()
    check_submodules()
    install_environment()
    PYBPOD_ENV, PIP, PYTHON_FILE, PYTHON = get_env_constants()
    install_extra_deps()
    install_pybpod_modules()
    conf_pybpod_settings()
    print("\nINFO: Installation concluded!\nYou should be good to go...\n")
