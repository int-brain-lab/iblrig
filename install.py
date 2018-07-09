#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-07-05 16:06:38
import platform
import os
import shutil
import json
import subprocess
import re
import sys

# Constants assuming Windows
IBL_ROOT_PATH = os.getcwd()
PYBPOD_PATH = os.path.join(IBL_ROOT_PATH, 'pybpod')
SUBMODULES_FOLDERS = [
    'Bonsai_workflows',
    'pybpod',
    'pybpod_projects',
    'water-calibration-plugin',
]


def get_pybpod_env(CONDA):
    # Find environment
    ENVS = subprocess.check_output([CONDA, "env", "list", "--json"])
    ENVS = json.loads(ENVS.decode('utf-8'))
    pat = re.compile("^.+pybpod-environment$")
    PYBPOD_ENV = [x for x in ENVS['envs'] if pat.match(x)]
    PYBPOD_ENV = PYBPOD_ENV[0] if PYBPOD_ENV else None
    return PYBPOD_ENV


def get_bonsai_path():
    try:
        import winreg as wr
        # HKEY_CLASSES_ROOT\Applications\Bonsai64.exe\shell\open\command
        Registry = wr.ConnectRegistry(None, wr.HKEY_CLASSES_ROOT)
        s = "Applications\\Bonsai64.exe\\shell\\open\\command"
        RawKey = wr.OpenKey(Registry, s)
        # print(RawKey)
        out = []
        try:
            i = 0
            while 1:
                name, value, type = wr.EnumValue(RawKey, i)
                out = [name, value, i]
                i += 1
        except WindowsError:
            print()

        bonsai_path = out[1].split()[0].strip('"')
        return bonsai_path
    except Exception:
        print('\nWARNING: BONSAI NOT PRESENT\nContinuing...\n')
        return None


BONSAI = get_bonsai_path()
BASE_ENV_FILE = 'environment-{}.yml'

if sys.platform in ['Windows', 'windows', 'win32']:
    ENV_FILE = BASE_ENV_FILE.format('windows-10')
    CONDA = "conda"
    SITE_PACKAGES = os.path.join("lib", "site-packages")
    PYBPOD_ENV = get_pybpod_env(CONDA)
    PIP = os.path.join(PYBPOD_ENV, 'Scripts', 'pip.exe')
    PYTHON_FILE = "python.exe"

elif sys.platform in ['Linux', 'linux']:
    ENV_FILE = BASE_ENV_FILE.format('ubuntu-17.10')
    CONDA = os.path.join(sys.prefix, "bin", "conda")
    SITE_PACKAGES = os.path.join("lib", "python3.6", "site-packages")
    PYBPOD_ENV = get_pybpod_env(CONDA)
    PIP = os.path.join(sys.prefix, "envs", "pybpod-environment", "bin", "pip")
    PYTHON_FILE = os.path.join("bin", "python")
elif sys.platform in ['Darwin', 'macOSx', 'osx']:
    ENV_FILE = BASE_ENV_FILE.format('macOSx')
    print("ERROR: macOSx is not supported yet\nInstallation aborted!")
else:
    print('\nERROR: Unsupported OS\nInstallation aborted!')


PYTHON = os.path.join(PYBPOD_ENV, PYTHON_FILE)


def check_dependencies():
    # Check if Git and conda are installed
    print('\nINFO: Checking for dependencies:\n')
    try:
        subprocess.check_output(["git", "--version"])
        subprocess.check_output([CONDA])
    except Exception as err:
        print(err)
    pass
    # Check if Bonsai is installed
    if BONSAI is None:
        print("WARNING: Bonsai not found, task will run with no visual stim\n",
              "\n",
              "Installation will proceed... \n")


def check_submodules():
    print('\nINFO: Checking submodules for initialization:\n')
    os.chdir(IBL_ROOT_PATH)
    for submodule in SUBMODULES_FOLDERS:
        if not os.listdir(os.path.join(IBL_ROOT_PATH, submodule)):
            subprocess.call(["git", "submodule", "update", "--init",
                             "--recursive"])


def install_environment():
    print('\nINFO: Installing pybpod-environment:\n')
    # Install pybpod-environment
    command = '{} env create -f {}'. format(CONDA, os.path.join(
        PYBPOD_PATH, ENV_FILE)).split()

    subprocess.call(command)


def install_extra_deps():
    print('\nINFO: Installing IBL specific dependencies:\n')
    if PYBPOD_ENV is None:
        msg = "Can't install extra dependencies, pybpod-environment not found"
        raise ValueError(msg)
        return
    # Define site-packages folder
    install_to = os.path.join(PYBPOD_ENV, SITE_PACKAGES)

    # Install extra depencencies using conda
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "scipy"])
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "pandas"])
    subprocess.call([CONDA, "install", "-n", "pybpod-environment",
                     "-c", "conda-forge", "python-sounddevice"])
    # Install extra depencencies using pip
    subprocess.call([PIP, "install", "--target={}".format(install_to),
                     "python-osc"])
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "requests"])
    subprocess.call([CONDA, "install", "-n", "pybpod-environment", "requests", "--update-deps"])

def install_pybpod():
    print('\nINFO: Installing pybpod:\n')
    if PYBPOD_ENV is None:
        msg = "Can't install pybpod, pybpod-environment not found"
        raise ValueError(msg)
        return
    # Install pybpod
    os.chdir(PYBPOD_PATH)
    subprocess.call([PYTHON, "install.py"])
    os.chdir('..')


def install_pybpod_modules():
    print('\nINFO: Installing pybpod modules and plugins:\n')
    subprocess.call([PIP, "install", "-e", "water-calibration-plugin"])
    os.chdir(PYBPOD_PATH)
    subprocess.call([PIP, "install", "-e", "pybpod-alyx-module"])
    subprocess.call([PIP, "install", "-e", "pybpod-analogoutput-module"])
    subprocess.call([PIP, "install", "-e", "pybpod-gui-plugin-trial-timeline"])
    os.chdir('..')


def conf_pybpod_settings():
    print('\nINFO: Configuring pybpod IBL project:\n')
    # Copy user settings
    src = os.path.join(IBL_ROOT_PATH, 'user_settings.py')
    shutil.copy(src, PYBPOD_PATH)


# def install_water_calibration():
#     PYBPOD_ENV = get_pybpod_env()
#     PYTHON = os.path.join(PYBPOD_ENV, PYTHON_FILE)
#     if PYBPOD_ENV is None:
#         msg = "Can't install pybpod, pybpod-environment not found"
#         raise ValueError(msg)
#         return
#     # Install water-calibration-plugin
#     os.chdir(os.path.join(IBL_ROOT_PATH, "water-calibration-plugin"))
#     subprocess.call([PYTHON, "setup.py", "install"])
#     os.chdir('..')


if __name__ == '__main__':
    check_dependencies()
    check_submodules()
    install_environment()
    install_extra_deps()
    install_pybpod()
    install_pybpod_modules()
    conf_pybpod_settings()
    # install_water_calibration()
    print("\nINFO: Done!\nYou should be good to go...\n")
    pass
