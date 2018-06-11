#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-06-11 14:22:09
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

if SYSTEM == 'Linux':
    ENV_FILE = ENV_FILE.format('ubuntu-17.10')
    CONDA = linux_conda
    SITE_PACKAGES = "lib/python3.6/site-packages"
    BONSAI = None
    PIP = "/home/nico/miniconda3/bin/pip"
    PYTHON = "/home/nico/miniconda3/envs/pybpod-environment/bin/python"
elif SYSTEM == 'Windows':
    ENV_FILE = ENV_FILE.format('windows-10')
    CONDA = "conda"
    SITE_PACKAGES = "lib/site-packages"
    BONSAI = os.path.join(os.getenv('USERPROFILE'),
                          "AppData/Local/Bonsai/Bonsai64.exe")
    WHERE_BONSAI = ["where", os.path.join(os.getenv('USERPROFILE'),
                    "AppData/Local/Bonsai:Bonsai64.exe")]
    PIP = "pip"
    # Find environment
    ENVS = subprocess.check_output([CONDA, "env", "list", "--json"])
    ENVS = json.loads(ENVS.decode('utf-8'))
    pat = re.compile("^.+/pybpod-environment$")
    PYBPOD_ENV = [x for x in ENVS['envs'] if pat.match(x)]
    PYBPOD_ENV = PYBPOD_ENV[0] if PYBPOD_ENV else None
    PYTHON = os.path.join(PYBPOD_ENV, "python.exe")
elif SYSTEM == 'Darwin':
    ENV_FILE = ENV_FILE.format('macOSx')
else:
    print('Unsupported OS')


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


def install_environment():
    # Install pybpod-environment
    command = '{} env create -f {}'. format(CONDA, os.path.join(
        PYBPOD_PATH, ENV_FILE)).split()

    subprocess.call(command)


def install_extra_deps():
    if PYBPOD_ENV is None:
        msg = "Can't install extra dependencies, pybpod-environment not found"
        raise ValueError(msg)
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
    # Install pybpod
    os.chdir(PYBPOD_PATH)
    subprocess.call([PYTHON, "install.py"])


def conf_pybpod_settings():
    # Copy user settings
    src = os.path.join(IBL_ROOT_PATH, 'user_settings.py')
    shutil.copy(src, PYBPOD_PATH)


def install_water_calibration():
    # Install water-calibration-plugin
    os.chdir(os.path.join(IBL_ROOT_PATH, "water-calibration-plugin"))
    subprocess.call([PYTHON, "setup.py", "install"])


if __name__ == '__main__':
    # check_dependencies()
    # install_environment()
    # install_extra_deps()
    # install_pybpod()
    # conf_pybpod_settings()
    # install_water_calibration()
