"""
Various get functions to return paths of folders and network drives
"""
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import yaml
from packaging import version

import iblrig
from ibllib.io import session_params
from ibllib.io.raw_data_loaders import load_settings
from iblutil.util import Bunch, setup_logger

log = setup_logger('iblrig')


def iterate_previous_sessions(subject_name, task_name, n=1, **kwargs):
    """
    This function iterates over the sessions of a given subject in both the remote and local path
    and searches for a given protocol name. It returns the information of the last n found
    matching protocols in the form of a dictionary
    :param subject_name:
    :param task_name: name of the protocol to look for in experiment description : '_iblrig_tasks_trainingChoiceWorld'
    :param **kwargs: optional arguments to be passed to iblrig.path_helper.get_local_and_remote_paths
    if not used, will use the arguments from iblrig/settings/iblrig_settings.yaml
    :return:
        list of dictionaries with keys: session_path, experiment_description, task_settings, file_task_data
    """
    rig_paths = get_local_and_remote_paths(**kwargs)
    sessions = _iterate_protocols(rig_paths.local_subjects_folder.joinpath(subject_name), task_name=task_name, n=n)
    if rig_paths.remote_subjects_folder is not None:
        remote_sessions = _iterate_protocols(rig_paths.remote_subjects_folder.joinpath(subject_name), task_name=task_name, n=n)
        if remote_sessions is not None:
            sessions.extend(remote_sessions)
        _, ises = np.unique([s['session_stub'] for s in sessions], return_index=True)
        sessions = [sessions[i] for i in ises]
    return sessions


def _iterate_protocols(subject_folder, task_name, n=1):
    """
    This function iterates over the sessions of a given subject and searches for a given protocol name
    It will then return the information of the last n found matching protocols in the form of a
    dictionary
    :param subject_folder:
    :param task_name: name of the protocol to look for in experiment description : '_iblrig_tasks_trainingChoiceWorld'
    :param n: number of maximum protocols to return
    :return:
        list of dictionaries with keys: session_stub, session_path, experiment_description, task_settings, file_task_data
    """
    protocols = []
    if subject_folder is None or Path(subject_folder).exists() is False:
        return protocols
    for file_experiment in sorted(subject_folder.rglob('_ibl_experiment.description*.yaml'), reverse=True):
        session_path = file_experiment.parent
        ad = session_params.read_params(file_experiment)
        if 'tasks' not in ad:
            continue
        if task_name not in ad['tasks'][0]:
            continue
        # reversed: we look for the last task first if the protocol ran twice
        for ad_task in reversed(ad['tasks']):
            adt = ad_task.get(task_name, None)
            if not adt:
                return
            task_settings = load_settings(session_path, task_collection=adt['collection'])
            if task_settings.get('NTRIALS', 43) < 42:  # we consider that under 42 trials it is a dud session
                continue
            protocols.append(
                Bunch(
                    {
                        'session_stub': '_'.join(file_experiment.parent.parts[-2:]),  # 2019-01-01_001
                        'session_path': file_experiment.parent,
                        'task_collection': adt['collection'],
                        'experiment_description': ad,
                        'task_settings': task_settings,
                        'file_task_data': session_path.joinpath(adt['collection'], '_iblrig_taskData.raw.jsonable'),
                    }
                )
            )
            if len(protocols) >= n:
                return protocols
    return protocols


def get_local_and_remote_paths(local_path=None, remote_path=None, lab=None):
    """
    Function used to parse input arguments to transfer commands. If the arguments are None, reads in the settings
    and returns the values from the files.
    local_subects_path alwawys has a fallback on the home directory / ilbrig_data
    remote_subjects_path has no fallback and will return None when all options are exhausted
    :param local_path:
    :param remote_path:
    :param lab:
    :return: dictionary, with following keys (example output)
       {'local_data_folder': PosixPath('C:/iblrigv8_data'),
        'remote_data_folder': PosixPath('Y:/'),
        'local_subjects_folder': PosixPath('C:/iblrigv8_data/mainenlab/Subjects'),
        'remote_subjects_folder': PosixPath('Y:/Subjects')}
    """
    iblrig_settings = load_settings_yaml()
    paths = Bunch({'local_data_folder': local_path, 'remote_data_folder': remote_path})
    if paths.local_data_folder is None:
        paths.local_data_folder = (
            Path(p) if (p := iblrig_settings['iblrig_local_data_path']) else Path.home().joinpath('iblrig_data')
        )
    if paths.remote_data_folder is None:
        paths.remote_data_folder = Path(p) if (p := iblrig_settings['iblrig_remote_data_path']) else None
    paths.local_subjects_folder = Path(paths.local_data_folder).joinpath(lab or iblrig_settings['ALYX_LAB'] or '', 'Subjects')
    paths.remote_subjects_folder = Path(p).joinpath('Subjects') if (p := paths.remote_data_folder) else None
    return paths


def load_settings_yaml(file_name='iblrig_settings.yaml', mode='raise'):
    """
    Load a yaml file from the settings folder.
    If the file_name is not absolute, it will be searched in the settings folder
    :param file_name: Path or str
    :return:
    """
    if not Path(file_name).is_absolute():
        file_name = Path(iblrig.__file__).parents[1].joinpath('settings', file_name)
    if not file_name.exists() and mode != 'raise':
        return {}
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
    if name.startswith('hardware') and version.parse(rs.get('VERSION', '0.0.0')) < version.Version('1.0.0'):
        if 'device_camera' in rs:
            log.info('Patching hardware settings; assuming left camera label')
            rs['device_cameras'] = {'left': rs.pop('device_camera')}
        rs['VERSION'] = '1.0.0'
    return rs


def get_iblrig_path() -> Path or None:
    return Path(iblrig.__file__).parents[1]


def get_commit_hash(folder: str):
    here = os.getcwd()
    os.chdir(folder)
    out = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    os.chdir(here)
    if not out:
        log.debug('Commit hash is empty string')
    log.debug(f'Found commit hash {out}')
    return out


def get_bonsai_path(use_iblrig_bonsai: bool = True) -> str:
    """Checks for Bonsai folder in iblrig. Returns string with bonsai executable path."""
    iblrig_folder = get_iblrig_path()
    bonsai_folder = next(
        (folder for folder in Path(iblrig_folder).glob('*') if folder.is_dir() and 'Bonsai' in folder.name), None
    )
    if bonsai_folder is None:
        return
    ibl_bonsai = os.path.join(bonsai_folder, 'Bonsai64.exe')
    if not Path(ibl_bonsai).exists():  # if Bonsai64 does not exist Bonsai v >2.5.0
        ibl_bonsai = os.path.join(bonsai_folder, 'Bonsai.exe')

    preexisting_bonsai = Path.home() / 'AppData/Local/Bonsai/Bonsai64.exe'
    if not preexisting_bonsai.exists():
        preexisting_bonsai = Path.home() / 'AppData/Local/Bonsai/Bonsai.exe'

    if use_iblrig_bonsai is True:
        bonsai = ibl_bonsai
    elif use_iblrig_bonsai is False and preexisting_bonsai.exists():
        bonsai = str(preexisting_bonsai)
    elif use_iblrig_bonsai is False and not preexisting_bonsai.exists():
        log.debug(f'NOT FOUND: {preexisting_bonsai}. Using packaged Bonsai')
        bonsai = ibl_bonsai
    log.debug(f'Found Bonsai executable: {bonsai}')
    return bonsai


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
