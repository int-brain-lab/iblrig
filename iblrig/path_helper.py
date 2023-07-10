"""
Various get functions to return paths of folders and network drives
"""
import logging
import os
import re
from pathlib import Path
import subprocess
import yaml

from packaging import version
import pandas as pd

from iblutil.util import Bunch
import iblrig

log = logging.getLogger("iblrig")


def load_settings_yaml(file_name='iblrig_settings.yaml'):
    """
    Load a yaml file from the settings folder.
    If the file_name is not absolute, it will be searched in the settings folder
    :param file_name: Path or str
    :return:
    """
    if not Path(file_name).is_absolute():
        file_name = Path(iblrig.__file__).parents[1].joinpath('settings', file_name)
    with open(file_name) as fp:
        rs = yaml.safe_load(fp)
    rs = patch_settings(rs, Path(file_name).stem)
    return Bunch(rs)


def patch_settings(rs: dict, name: str) -> dict:
    """
    Update loaded settings files to ensure compatibility with latest version.

    Parameters
    ----------
    rs : dict
        A loaded settings file.
    name : str
        The name of the settings file, e.g. 'hardware_settings'.

    Returns
    -------
    dict
        The updated settings.
    """
    if name.startswith('hardware'):
        if version.parse(rs.get('VERSION', '0.0.0')) < version.Version('1.0.0'):
            if 'device_camera' in rs:
                log.info('Patching hardware settings; assuming left camera label')
                rs['device_cameras'] = {'left': rs.pop('device_camera')}
            rs['VERSION'] = '1.0.0'
    return rs


def get_iblrig_path() -> Path or None:
    return Path(iblrig.__file__).parents[1]


def get_iblrig_params_path() -> Path or None:
    return get_iblrig_path().joinpath("pybpod_fixtures")


def get_commit_hash(folder: str):
    here = os.getcwd()
    os.chdir(folder)
    out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    os.chdir(here)
    if not out:
        log.debug("Commit hash is empty string")
    log.debug(f"Found commit hash {out}")
    return out


def get_bonsai_path(use_iblrig_bonsai: bool = True) -> str:
    """Checks for Bonsai folder in iblrig. Returns string with bonsai executable path."""
    iblrig_folder = get_iblrig_path()
    bonsai_folder = next((folder for folder in Path(
        iblrig_folder).glob('*') if folder.is_dir() and 'Bonsai' in folder.name), None)
    if bonsai_folder is None:
        return
    ibl_bonsai = os.path.join(bonsai_folder, "Bonsai64.exe")
    if not Path(ibl_bonsai).exists():  # if Bonsai64 does not exist Bonsai v >2.5.0
        ibl_bonsai = os.path.join(bonsai_folder, "Bonsai.exe")

    preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai64.exe"
    if not preexisting_bonsai.exists():
        preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai.exe"

    if use_iblrig_bonsai is True:
        BONSAI = ibl_bonsai
    elif use_iblrig_bonsai is False and preexisting_bonsai.exists():
        BONSAI = str(preexisting_bonsai)
    elif use_iblrig_bonsai is False and not preexisting_bonsai.exists():
        log.debug(f"NOT FOUND: {preexisting_bonsai}. Using packaged Bonsai")
        BONSAI = ibl_bonsai
    log.debug(f"Found Bonsai executable: {BONSAI}")

    return BONSAI


def iterate_collection(session_path: str, collection_name='raw_task_data') -> str:
    """
    Given a session path returns the next numbered collection name.

    Parameters
    ----------
    session_path : str
        The session path containing zero or more numbered collections.
    collection_name : str
        The collection name without the _NN suffix.

    Returns
    -------
    str
        The next numbered collection name.

    Examples
    --------
    In a folder where there are no raw task data folders

    >>> iterate_collection('./subject/2020-01-01/001')
    'raw_task_data_00'

    In a folder where there is one raw_imaging_data_00 folder

    >>> iterate_collection('./subject/2020-01-01/001', collection_name='raw_imaging_data')
    'raw_imaging_data_01'
    """
    if not Path(session_path).exists():
        return f'{collection_name}_00'
    collections = filter(Path.is_dir, Path(session_path).iterdir())
    collection_names = map(lambda x: x.name, collections)
    tasks = sorted(filter(re.compile(f'{collection_name}' + '_[0-9]{2}').match, collection_names))
    if len(tasks) == 0:
        return f'{collection_name}_00'
    return f'{collection_name}_{int(tasks[-1][-2:]) + 1:02}'
