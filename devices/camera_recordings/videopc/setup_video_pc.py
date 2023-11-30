#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: videopc/setup_rig.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Wednesday, August 25th 2021, 1:17:33 pm
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import requests

# Remove old iblenv environment
# Create iblenv python environment with python=3.7 using conda
# Activate the newly created iblenv python environment
# Install ibllib using pip
# Download PySpin python library from shared drive
# Unzip PySpin python library to temp folder
# Install PySpin python library to environment


def download_file_from_google_drive(id, destination):
    URL = "https://docs.google.com/uc?export=download"

    session = requests.Session()

    response = session.get(URL, params={'id': id}, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {'id': id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)

    save_response_content(response, destination)


def get_confirm_token(response):

    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None


def save_response_content(response, destination):
    CHUNK_SIZE = 32768

    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)


def download_pyspin(destination_file=None):
    """Download pyspin from IBL shared drive
    """
    if destination_file is None:
        destination_file = Path().home() / "Downloads" / "pyspin.zip"
    # Download the spinnaker-python library
    print("\n\nDownloading the spinnaker-python library\n")
    # file_id = '1A-tiVYnZvcZJA0LbLT51B6mjmXlnmwRq'  # Old file
    file_id = '1Fmo2fNZRMjwhI1_b-9vxq33qgW3qEpHp'
    download_file_from_google_drive(file_id, destination_file)


def unzip_pyspin(source_file=None, destination_dir=None):
    """Unzip the pyspin library
    """
    if source_file is None:
        source_file = Path().home() / "Downloads" / "pyspin.zip"
    else:
        source_file = Path(source_file)
    if destination_dir is None:
        destination_dir = source_file.parent / source_file.stem
        if not destination_dir.exists():
            destination_dir.mkdir()

    print("Unzipping pyspin...")
    with zipfile.ZipFile(source_file, 'r') as zip_ref:
        zip_ref.extractall(destination_dir)

    return destination_dir


def get_env_folder(env_name: str = "iblenv") -> str:
    """get_env_folder Return conda folder of [env_name] environment

    :param env_name: name of conda environment to look for, defaults to 'iblenv'
    :type env_name: str, optional
    :return: folder path of conda environment
    :rtype: str
    """
    all_envs = subprocess.check_output(["conda", "env", "list", "--json"])
    all_envs = json.loads(all_envs.decode("utf-8"))
    pat = re.compile(f"^.+{env_name}$")
    env = [x for x in all_envs["envs"] if pat.match(x)]
    env = env[0] if env else None
    return env


def get_env_pip(env_name: str = "iblenv", rpython=False):
    env = get_env_folder(env_name=env_name)
    if sys.platform in ["Windows", "windows", "win32"]:
        pip = os.path.join(env, "Scripts", "pip.exe")
        python = os.path.join(env, "python.exe")
    else:
        pip = os.path.join(env, "bin", "pip")
        python = os.path.join(env, "bin", "python")

    return pip if not rpython else python


def pip_install_pyspin(env_name='iblenv', pyspin_whl=None):
    """Install pyspin to python environment
    """
    pip = get_env_pip(env_name=env_name)

    if pyspin_whl is None:
        destination_dir = Path().home() / "Downloads" / "pyspin"
        if sys.platform in ["Windows", "windows", "win32"]:
            pyspin_whl = destination_dir / "spinnaker_python-2.0.0.147-cp37-cp37m-win_amd64.whl"
        else:
            pyspin_whl = destination_dir / "spinnaker_python-2.0.0.147-cp37-cp37m-linux_x86_64.whl"

    print("\n\nINFO: Installing PySpin python library\n")
    os.system(f"{pip} install {pyspin_whl}")


def pip_install_ibllib(env_name='iblenv'):
    """Install ibllib to python environment
    """
    pip = get_env_pip(env_name=env_name)

    print("\n\nINFO: Installing ibllib python library\n")
    os.system(f"{pip} install -U ibllib --use-feature=2020-resolver")


def create_environment(env_name="iblenv", use_conda_yaml=False, force=False):
    if use_conda_yaml:
        os.system("conda env create -f environment.yml")
        return
    print(f"\n\nINFO: Installing {env_name}:")
    print("N" * 79)
    # Checks if env is already installed
    env = get_env_folder(env_name=env_name)
    print(env)
    # Creates commands
    create_command = f"conda create -y -n {env_name} python=3.7"
    remove_command = f"conda env remove -y -n {env_name}"
    if not env:
        os.system(create_command)
    else:
        print(
            "Found pre-existing environment in {}".format(env),
            "\nDo you want to reinstall the environment? (y/n):",
        )
        user_input = input() if not force else "y"
        print(user_input)
        if user_input == "y":
            os.system(remove_command)
            shutil.rmtree(env, ignore_errors=True)
            return create_environment(env_name=env_name, force=force)
        elif user_input != "n" and user_input != "y":
            print("Please answer 'y' or 'n'")
            return create_environment(env_name=env_name, force=force)
        elif user_input == "n":
            return

    print("N" * 79)
    print(f"{env_name} installed.")


def install_bonsai():
    if sys.platform not in ["Windows", "windows", "win32"]:
        print("\n\nSkippinig Bonsai installation now on Windows platform")
        return
    if Path(os.getcwd()).joinpath("bonsai", "bin", "Bonsai.exe").exists():
        print("\n\nBonsai already installed")
        user_input = input("Do you want to reinstall Bonsai? (y/n): ")
        user_input = user_input.lower()
        print(user_input)
        if user_input == "y":
            bbin_folder = Path(os.getcwd()).joinpath("bonsai", "bin")
            if bbin_folder.exists():
                shutil.rmtree(bbin_folder, ignore_errors=True)
            os.system("git reset --hard")
            return install_bonsai()
        elif user_input != "n" and user_input != "y":
            print("Please answer 'y' or 'n'")
            return install_bonsai()
        return
    here = os.getcwd()
    os.chdir("./bonsai/bin/")
    os.system("setup.bat")
    os.chdir(here)
    return


def setup_videopc(env_name='iblenv'):
    """Setup the iblrig video PC.
    Create python environment,
    Install ibllib, (+ iblutil?)
    Download, unzip, and install the spinnaker-python library
    """

    # Create python environment using conda

    print("\n\nCreating python environment\n")
    create_environment(env_name=env_name, force=False)

    # Install ibllib
    print("\n\nInstalling ibllib\n")
    pip_install_ibllib(env_name=env_name)

    # Download and install the spinnaker-python library
    print("\n\nDownloading and installing the spinnaker-python library\n")
    download_pyspin()
    unzip_pyspin()
    pip_install_pyspin(env_name=env_name)
    install_bonsai()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Setup video PC environment and dependencies')
    parser.add_argument(
        '--env-name', default='iblenv', required=False,
        help="Environment name, defaults to [iblenv]")
    args = parser.parse_args()

    setup_videopc(env_name=args.env_name)
