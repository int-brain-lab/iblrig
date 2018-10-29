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
    SITE_PACKAGES = os.path.join("lib", "python3.6", "site-packages")  # TODO: find latest python instalation!!n
elif sys.platform in ['Darwin', 'macOSx', 'osx']:
    print("ERROR: macOSx is not supported yet\nInstallation aborted!")
else:
    print('\nERROR: Unsupported OS\nInstallation aborted!')


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
        return
    else:
        print('\nERROR: Unsupported OS\nInstallation aborted!')
        return

    subprocess.call([python, '-m', 'pip', 'install', '--upgrade', 'pip'])
    subprocess.call([pip, 'install', '--upgrade', 'pip'])

    return pip, python


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
    create_command = '{} create -y -n iblenv python=3.6.6'. format(conda).split()
    remove_command = '{} env remove -y -n iblenv'. format(conda).split()
    # Installes the env
    if env:
        print("Found pre-existing environment in {}".format(env),
              "\nDo you want to reinstall the environment? (y/n):")
        user_input = input()
        if user_input == 'y':
            subprocess.call(remove_command)
            install_environment(conda)
        elif user_input != 'n' and user_input != 'y':
            print("Please answer 'y' or 'n'")
            install_environment(conda)
        elif user_input == 'n':
            pass
    else:
        subprocess.call(create_command)

    print("N" * 79)
    print("iblenv installed.")


def install_iblrig_requirements(conda):
    print('\n\nINFO: Installing IBLrig requirements:')
    print("N" * 79)
    iblenv = get_iblenv(conda)
    pip, _ = get_iblenv_pip_n_python(conda)
    if iblenv is None:
        msg = "Can't install iblrig requirements, iblenv not found"
        raise ValueError(msg)
    # Define site-packages folder
    install_to = os.path.join(iblenv, SITE_PACKAGES)

    print("N" * 39, 'Installing scipy')
    subprocess.call([CONDA, "install", "-y",
                     "-n", "iblenv", "scipy"])
    print("N" * 39, 'Installing sounddevice')
    subprocess.call([CONDA, "install", "-y", "-n", "iblenv",
                     "-c", "conda-forge", "python-sounddevice"])
    print("N" * 39, 'Installing requests')
    subprocess.call([CONDA, "install", "-y", "-n",
                     "iblenv", "requests"])
    print("N" * 39, 'Installing requests dependencies')
    subprocess.call([CONDA, "install", "-y",
                     "-n", "iblenv", "requests", "--update-deps"])
    # Install extra depencencies using pip
    print("N" * 39, '(pip) Installing python-osc')
    subprocess.call([pip, "install", "python-osc"])
    subprocess.call([pip, "install", "cython"])
    print("N" * 39, '(pip) Installing PyBpod')
    subprocess.call([pip, "install", "pybpod", "--upgrade"])
    subprocess.call([pip, "install", "-U", "pybpod"])
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
            return
        elif user_input == 'y':
            shutil.rmtree(ibllib_path)
            subprocess.call(["git", "clone",
                             'https://github.com/int-brain-lab/ibllib.git'])
        elif user_input != 'n' and user_input != 'y':
            print("\n Please select either y of n")
            clone_ibllib()
    else:
        subprocess.call(["git", "clone",
                         'https://github.com/int-brain-lab/ibllib.git'])

    os.chdir(IBLRIG_ROOT_PATH)
    print("N" * 79)
    print("ibllib cloned.")


def install_ibllib(conda):
    print('\n\nINFO: Installing ibllib:')
    print("N" * 79)
    iblenv = get_iblenv(conda)
    pip, _ = get_iblenv_pip_n_python(conda)
    if iblenv is None:
        msg = "Can't install ibllib to iblenv, iblenv not found"
        raise ValueError(msg)
    # Install iblenv
    os.chdir(IBLRIG_ROOT_PATH.parent / 'ibllib/python')
    subprocess.call([pip, "install", "-e", "."])
    os.chdir(IBLRIG_ROOT_PATH)
    print("N" * 79)
    print("INFO: ibllib installed.")


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
        check_dependencies(CONDA)
        install_environment(CONDA)
        install_iblrig_requirements(CONDA)
        clone_ibllib()
        install_ibllib(CONDA)
        print("\nIts time to install Bonsai:\n  Please install all packages.",
              "\nIMPORTANT: the Bonsai.Bpod package is in the pre-release tab.")
        install_bonsai()
        print("\n\nINFO: iblrig installed, you should be good to go!")
    except IOError as msg:
        print(msg, "\n\nSOMETHING IS WRONG: Bad! Bad install file!")

    print(".")
