#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-06-08 11:04:05
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from packaging.version import parse as version

from iblrig import envs

# BEGIN CONSTANT DEFINITION
IBLRIG_ROOT_PATH = Path.cwd()

if sys.platform not in ["Windows", "windows", "win32"]:
    print("\nWARNING: Unsupported OS\nInstallation might not work!")

try:
    print("\n\n--->Cleaning up conda cache")
    os.system("conda clean -q -y --all")
    print("\n--->conda cache... OK")
except BaseException as e:
    print(e)
    raise BaseException("Could not clean conda cache, is conda installed? aborting...")

MC = (
    "conda"
    if "mamba"
    not in str(subprocess.check_output([os.environ["CONDA_EXE"], "list", "-n", "base", "--json"]))
    else "mamba"
)

if MC == "conda":
    print("\n\n--->mamba not found")
    try:
        print("\n\n--->Installing mamba")
        os.system("conda install mamba -q -y -n base -c conda-forge")
        print("\n--->mamba installed... OK")
        MC = "mamba"
    except BaseException as e:
        print(e)
        print("Could not install mamba, using conda...")
        MC = "conda"
# END CONSTANT DEFINITION


def check_update_dependencies():
    # Check if Git and conda are installed
    print("\n\nINFO: Checking for dependencies:")
    print("N" * 79)
    if "packaging" not in str(subprocess.check_output([f"{MC}", "list", "--json"])):
        try:
            print("\n\n--->Installing packaging")  # In case of miniconda install packaging
            os.system(f"{MC} install packaging -q -y -n base -c defaults")
        except BaseException as e:
            print(e)
            raise SystemError("Could not install packaging, aborting...")

    conda_version = str(subprocess.check_output([f"{MC}", "-V"])).split(" ")[1].split("\\n")[0]
    python_version = (
        str(subprocess.check_output(["python", "-V"])).split(" ")[1].split("\\n")[0]
    ).strip("\\r")
    pip_version = str(subprocess.check_output(["pip", "-V"])).split(" ")[1]

    if version(conda_version) < version("4.10.3"):
        try:
            print("\n\n--->Updating base conda")
            os.system(f"{MC} update -q -y -n base -c defaults conda")
            print("\n--->conda update... OK")
        except BaseException as e:
            print(e)
            raise SystemError("Could not update conda, aborting install...")

    if version(python_version) < version("3.7.11"):
        try:
            print("\n\n--->Updating base environment python")
            os.system(f"{MC} update -q -y -n base -c defaults python>=3.8")
            print("\n--->python update... OK")
        except BaseException as e:
            print(e)
            raise SystemError("Could not update python, aborting install...")

    if version(pip_version) < version("20.2.4"):
        try:
            print("\n\n--->Reinstalling pip, setuptools, wheel...")
            os.system(f"{MC} install -q -y -n base -c defaults pip>=20.2.4 --force-reinstall")
            os.system(f"{MC} update -q -y -n base -c defaults setuptools wheel")
            print("\n--->pip, setuptools, wheel upgrade... OK")
        except BaseException as e:
            print(e)
            raise SystemError("Could not reinstall pip, setuptools, wheel aborting install...")

    try:
        subprocess.check_output(["git", "--version"])
    except BaseException as e:
        print(e, "\ngit not found trying to install...")
        try:
            print("\n\n--->Installing git")
            os.system(f"{MC} install -q -y git")
            print("\n\n--->git... OK")
        except BaseException as e:
            print(e)
            raise SystemError("Could not install git, aborting install...")

    # try:
    #     print("\n\n--->Updating remaning base packages...")
    #     os.system(f"{MC} update -q -y -n base -c defaults --all")
    #     print("\n--->Update of remaining packages... OK")
    # except BaseException as e:
    #     print(e)
    #     print("Could not update remaining packages, trying to continue install...")

    print("N" * 79)
    print("All dependencies OK.")
    return 0


def create_ibllib_env(env_name: str = "ibllib"):
    """create_ibllib_env Create conda environment named [env_name]

    :param env_name: name of conda environment to be created, defaults to 'ibllib'
    :type env_name: str, optional
    :return: 0 if success, 1 otherwise
    :rtype: int
    """
    print(f"\n\nINFO: Creating environment {env_name}...")
    print("N" * 79)
    env = envs.get_env_folder(env_name=env_name)
    if not env:
        try:
            print("\n\n--->Creating environment")
            os.system(f"{MC} create -q -y -n {env_name} -c defaults python=3.8")
            pip = envs.get_env_pip(env_name)
            os.system(f"{pip} install --no-warn-script-location ibllib")
            print("\n--->Environment created... OK")
        except BaseException as e:
            print(e)
            raise SystemError(f"Could not create {env_name} environment, aborting...")
    else:
        print(f"\n\nINFO: Environment {env_name} already exists, reinstalling.")
        remove_command = f"{MC} env remove -q -y -n {env_name}"
        os.system(remove_command)
        shutil.rmtree(env, ignore_errors=True)
        return create_ibllib_env(env_name=env_name)
    print("N" * 79)
    return 0


def create_environment(env_name="iblenv", use_conda_yaml=False, resp=False):
    if use_conda_yaml:
        os.system(f"{MC} env create -f environment.yaml")
        return
    print(f"\n\nINFO: Creating {env_name}:")
    print("N" * 79)
    # Checks if env is already installed
    env = envs.get_env_folder(env_name=env_name)
    print(env)
    # Creates commands
    create_command = f"{MC} create -q -y -n {env_name} python==3.7.11"
    remove_command = f"{MC} env remove -q -y -n {env_name}"
    # Installes the env
    if env:
        print(
            "Found pre-existing environment in {}".format(env),
            "\nDo you want to reinstall the environment? (y/n):",
        )
        user_input = input() if not resp else resp
        print(user_input)
        if user_input == "y":
            os.system(remove_command)
            shutil.rmtree(env, ignore_errors=True)
            return create_environment(env_name=env_name)
        elif user_input != "n" and user_input != "y":
            print("Please answer 'y' or 'n'")
            return create_environment(env_name=env_name)
        elif user_input == "n":
            return
    else:
        os.system(create_command)
        python = envs.get_env_python(env_name=env_name)
        update_pip_command = f"{python} -m pip install --upgrade pip setuptools wheel"
        os.system(update_pip_command)
        os.system(f"{MC} install -q -y -n {env_name} git")

    print("N" * 79)
    print(f"{env_name} installed.")


def install_iblrig(env_name: str = "iblenv") -> None:
    print(f"\n\nINFO: Installing iblrig in {env_name}:")
    print("N" * 79)
    pip = envs.get_env_pip(env_name=env_name)
    os.system(f"{pip} install --no-warn-script-location -e .")
    print("N" * 79)
    print(f"iblrig installed in {env_name}.")


def configure_iblrig_params(env_name: str = "iblenv", resp=False):
    print("\n\nINFO: Setting up default project config in ../iblrig_params:")
    print("N" * 79)
    iblenv = envs.get_env_folder(env_name=env_name)
    if iblenv is None:
        msg = f"Can't configure iblrig_params, {env_name} not found"
        raise ValueError(msg)
    python = envs.get_env_python(env_name=env_name)
    iblrig_params_path = IBLRIG_ROOT_PATH.parent / "iblrig_params"
    if iblrig_params_path.exists():
        print(
            f"Found previous configuration in {str(iblrig_params_path)}",
            "\nDo you want to reset to default config? (y/n)",
        )
        user_input = input() if not resp else resp
        print(user_input)
        if user_input == "n":
            return
        elif user_input == "y":
            subprocess.call([python, "setup_pybpod.py", str(iblrig_params_path)])
        elif user_input != "n" and user_input != "y":
            print("\n Please select either y of n")
            return configure_iblrig_params(env_name=env_name)
    else:
        iblrig_params_path.mkdir(parents=True, exist_ok=True)
        subprocess.call([python, "setup_pybpod.py", str(iblrig_params_path)])


def install_bonsai(resp=False):
    print("\n\nDo you want to install Bonsai now? (y/n):")
    user_input = input() if not resp else resp
    print(user_input)
    if user_input == "y":
        if sys.platform not in ["Windows", "windows", "win32"]:
            print("Skipping Bonsai installation on non-Windows platforms")
            return
        # Remove Bonsai folder, git pull, and setup Bonsai
        bonsai_folder = os.path.join(IBLRIG_ROOT_PATH, "Bonsai")
        shutil.rmtree(bonsai_folder, ignore_errors=True)
        subprocess.call(["git", "fetch", "--all", "-q"])
        subprocess.call(["git", "reset", "--hard", "-q"])
        subprocess.call(["git", "pull", "-q"])
        # Setup Bonsai
        here = os.getcwd()
        os.chdir(bonsai_folder)
        bonsai_exe = os.path.join(IBLRIG_ROOT_PATH, "Bonsai", "Bonsai64.exe")
        if Path(bonsai_exe).exists():  # Either the bonsai64.exe exisits for old deplotment or
            subprocess.call(bonsai_exe)  # call to restore state, will halt until window close
        else:  # the new deployment will download the bonsai exe
            subprocess.call("setup.bat")
        os.chdir(here)
    elif user_input != "n" and user_input != "y":
        print("Please answer 'y' or 'n'")
        return install_bonsai()
    elif user_input == "n":
        return


def setup_ONE(resp=False):
    """
    """
    print("\n\nINFO: ONE setup")
    print("N" * 79)
    print("\n\nDo you want to install ONE now? (y/n):")
    user_input = input() if not resp else resp
    print(user_input)
    if user_input == "y":
        try:
            python = envs.get_env_python(env_name="ibllib")
            os.system(f'{python} -c "from one.api import ONE; ONE()"')
        except BaseException as e:
            print(
                e, "\n\nONE setup incomplete please set up ONE manually",
            )
    elif user_input != "n" and user_input != "y":
        print("Please answer 'y' or 'n'")
        return setup_ONE()
    elif user_input == "n":
        pass
    print("N" * 79)
    return


def main(args):
    try:
        check_update_dependencies()
        create_environment(
            env_name=args.env_name, use_conda_yaml=args.use_conda, resp=args.reinstall_response,
        )
        create_ibllib_env()
        install_iblrig(env_name=args.env_name)
        configure_iblrig_params(env_name=args.env_name, resp=args.config_response)
        setup_ONE(resp=args.ONE_response)
        install_bonsai(resp=args.bonsai_response)
    except BaseException as msg:
        print(msg, "\n\nSOMETHING IS WRONG: Bad! Bad install file!")
    return


if __name__ == "__main__":
    RESPONSES = ["y", "n", False]
    parser = argparse.ArgumentParser(description="Install iblrig")
    parser.add_argument(
        "--env-name",
        "-n",
        required=False,
        default="iblenv",
        help="Environment name for IBL rig installation",
    )
    parser.add_argument(
        "--use-conda",
        required=False,
        default=False,
        action="store_true",
        help="Use conda YAML file to creat environment and install deps.",
    )
    parser.add_argument(
        "--config-response",
        required=False,
        default=False,
        help="Use this response when if asked for resetting default config",
    )
    parser.add_argument(
        "--bonsai-response",
        required=False,
        default=False,
        help="Use this response when asked if you want to install Bonsai",
    )
    parser.add_argument(
        "--reinstall-response",
        required=False,
        default=False,
        help="Use this response when if asked to reinstall env",
    )
    parser.add_argument(
        "--ONE-response",
        required=False,
        default=False,
        help="Use this response when if asked to setuo ONE",
    )

    args = parser.parse_args()
    RUN = 1
    if args.use_conda:  # bool
        args.env_name = "iblenv"
    if args.bonsai_response not in RESPONSES:
        print(
            f"Invalid --bonsai-response argument {args.bonsai_response}",
            "\nPlease use {RESPONSES})",
        )
        RUN = 0
    if args.config_response not in RESPONSES:
        print(
            f"Invalid --config-response argument {args.config_response}",
            "\nPlease use {RESPONSES})",
        )
        RUN = 0
    if args.reinstall_response not in RESPONSES:
        print(
            f"Invalid --reinstall-response argument {args.reinstall_response}",
            "\nPlease use {RESPONSES})",
        )
        RUN = 0
    if args.ONE_response not in RESPONSES:
        print(
            f"Invalid --reinstall-response argument {args.reinstall_response}",
            "\nPlease use {RESPONSES})",
        )
        RUN = 0

    if RUN:
        main(args)

    print("\n\nINFO: iblrig installation EoF")
