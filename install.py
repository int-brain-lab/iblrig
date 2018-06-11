# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-06-11 12:48:36
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
elif SYSTEM == 'Windows':
    ENV_FILE = ENV_FILE.format('windows-10')
    CONDA = "conda"
    SITE_PACKAGES = "lib/site-packages"
    BONSAI = "C:\\"
elif SYSTEM == 'Darwin':
    ENV_FILE = ENV_FILE.format('macOSx')
    CONDA = "conda"
    BONSAI = None
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


def install_environment():
    # Install pybpod-environment
    command = '{} env create -f {}'. format(CONDA, os.path.join(
        PYBPOD_PATH, ENV_FILE)).split()

    subprocess.call(command)


def install_extra_deps():
    # Find environment
    envs = subprocess.check_output([CONDA, "env", "list", "--json"])
    envs = json.loads(envs.decode('utf-8'))
    pat = re.compile("^.+/pybpod-environment$")
    pybpod_env = [x for x in envs['envs'] if pat.match(x)]
    pybpod_env = pybpod_env[0] if pybpod_env else None
    if pybpod_env is None:
        msg = "Can't install extra dependencies, pybpod-environment not found"
        raise ValueError(msg)
    # Define site-packages folder
    install_to = os.path.join(pybpod_env, SITE_PACKAGES)

    # Install extra depencencies using conda
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "scipy"])
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "pandas"])
    # Install extra depencencies using pip
    subprocess.call(["pip", "install", "--target={}",
                     "python-osc".format(install_to)])
    subprocess.call(["pip", "install", "--target={}",
                     "sounddevice".format(install_to)])


def install_pybpod():
    # Install pybpod
    install = os.path.join(PYBPOD_PATH, "install.py")
    subprocess.call(["python", install])


def conf_pybpod_settings():
    # Copy user settings
    src = os.path.join(IBL_ROOT_PATH, 'user_settings.py')
    shutil.copy(src, PYBPOD_PATH)


def install_water_calibration():
    # Install water-calibration-plugin
    setup = os.path.join(IBL_ROOT_PATH, "water-calibration-plugin", "setup.py")
    subprocess.call(["python", setup, "install"])


if __name__ == '__main__':
    check_dependencies()
    install_environment()
    install_extra_deps()
    install_pybpod()
    conf_pybpod_settings()
    install_water_calibration()
