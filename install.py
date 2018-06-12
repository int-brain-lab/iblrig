#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-06-12 10:42:16
import platform
import os
import shutil
import json
import subprocess
import re

# Constants
linux_conda = "/home/nico/miniconda3/bin/conda"
IBL_ROOT_PATH = os.getcwd()
PYBPOD_PATH = os.path.join(IBL_ROOT_PATH, 'pybpod')
SUBMODULES_FOLDERS = [
    'Bonsai_workflows',
    'pybpod',
    'pybpod_projects',
    'water-calibration-plugin',
]
# Check on which system you are running and define env_file
SYSTEM = platform.system()
ENV_FILE = 'environment-{}.yml'

if SYSTEM == 'Windows':
    ENV_FILE = ENV_FILE.format('windows-10')
    CONDA = "conda"
    SITE_PACKAGES = "lib/site-packages"
    BONSAI = os.path.join(os.getenv('USERPROFILE'),
                          "AppData/Local/Bonsai/Bonsai64.exe")
    WHERE_BONSAI = ["where", os.path.join(os.getenv('USERPROFILE'),
                    "AppData/Local/Bonsai:Bonsai64.exe")]
    PIP = "pip"
    PYTHON_FILE = "python.exe"
elif SYSTEM == 'Linux':
    ENV_FILE = ENV_FILE.format('ubuntu-17.10')
    CONDA = linux_conda
    SITE_PACKAGES = "lib/python3.6/site-packages"
    BONSAI = None
    PIP = "/home/nico/miniconda3/bin/pip"
    PYTHON_FILE = "bin/python"
elif SYSTEM == 'Darwin':
    ENV_FILE = ENV_FILE.format('macOSx')
else:
    print('Unsupported OS')


def get_pybpod_env():
    # Find environment
    ENVS = subprocess.check_output([CONDA, "env", "list", "--json"])
    ENVS = json.loads(ENVS.decode('utf-8'))
    pat = re.compile("^.+pybpod-environment$")
    PYBPOD_ENV = [x for x in ENVS['envs'] if pat.match(x)]
    PYBPOD_ENV = PYBPOD_ENV[0] if PYBPOD_ENV else None
    return PYBPOD_ENV


def check_dependencies():
    # Check if Git and conda are installed
    try:
        subprocess.check_output(["git", "--version"])
        subprocess.check_output([CONDA])
    except Exception as err:
        print(err)
    pass
    # Check if Bonsai is installed
    try:
        subprocess.call(WHERE_BONSAI)
    except Exception as err:
        print(err, "\n",
              "WARNING: Bonsai not found in its default folder.\n",
              "Please install Bonsai in its default folder.\n",
              "Installation will proceed...\n")


def check_submodules():
    os.chdir(IBL_ROOT_PATH)
    for submodule in SUBMODULES_FOLDERS:
        if not os.listdir(os.path.join(IBL_ROOT_PATH, submodule)):
            subprocess.call(["git", "submodule", "update", "--init",
                             "--recursive"])


def install_environment():
    # Install pybpod-environment
    command = '{} env create -f {}'. format(CONDA, os.path.join(
        PYBPOD_PATH, ENV_FILE)).split()

    subprocess.call(command)


def install_extra_deps():
    PYBPOD_ENV = get_pybpod_env()
    if PYBPOD_ENV is None:
        msg = "Can't install extra dependencies, pybpod-environment not found"
        raise ValueError(msg)
        return
    # Define site-packages folder
    install_to = os.path.join(PYBPOD_ENV, SITE_PACKAGES)

    # Install extra depencencies using conda
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "scipy"])
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "pandas"])
    # Install extra depencencies using pip
    subprocess.call([PIP, "install", "--target={}".format(install_to),
                     "python-osc"])
    subprocess.call([PIP, "install", "--target={}".format(install_to),
                     "sounddevice"])


def install_pybpod():
    PYBPOD_ENV = get_pybpod_env()
    PYTHON = os.path.join(PYBPOD_ENV, PYTHON_FILE)
    if PYBPOD_ENV is None:
        msg = "Can't install pybpod, pybpod-environment not found"
        raise ValueError(msg)
        return
    # Install pybpod
    os.chdir(PYBPOD_PATH)
    subprocess.call([PYTHON, "install.py"])


def conf_pybpod_settings():
    # Copy user settings
    src = os.path.join(IBL_ROOT_PATH, 'user_settings.py')
    shutil.copy(src, PYBPOD_PATH)


def install_water_calibration():
    PYBPOD_ENV = get_pybpod_env()
    PYTHON = os.path.join(PYBPOD_ENV, PYTHON_FILE)
    if PYBPOD_ENV is None:
        msg = "Can't install pybpod, pybpod-environment not found"
        raise ValueError(msg)
        return
    # Install water-calibration-plugin
    os.chdir(os.path.join(IBL_ROOT_PATH, "water-calibration-plugin"))
    subprocess.call([PYTHON, "setup.py", "install"])
    os.chdir('..')


if __name__ == '__main__':
    check_dependencies()
    check_submodules()
    install_environment()
    install_extra_deps()
    install_pybpod()
    conf_pybpod_settings()
    install_water_calibration()
    pass
