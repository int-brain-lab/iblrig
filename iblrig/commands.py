import argparse
import datetime
import json
from pathlib import Path
from typing import List, Tuple

import yaml
import shutil

from iblutil.util import setup_logger
from ibllib.io import raw_data_loaders
from iblrig.transfer_experiments import BehaviorCopier, VideoCopier, EphysCopier
import iblrig
from iblrig.hardware import Bpod
from iblrig.path_helper import load_settings_yaml, get_local_and_remote_paths
from iblrig.online_plots import OnlinePlots
from iblrig.raw_data_loaders import load_task_jsonable

logger = setup_logger('iblrig', level='INFO')


def _transfer_parser(description: str) -> argparse.ArgumentParser:
    """
    Create an ArgumentParser for transfer scripts.

    This function creates an ArgumentParser object with specific arguments for a
    script related to data transfer. It defines command-line arguments for
    defining local and remote data paths and enabling the dry run mode.

    Parameters
    ----------
    description : str
        A brief description of the script's purpose.

    Returns
    -------
    argparse.ArgumentParser
        An ArgumentParser object with pre-defined arguments.
    """
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     argument_default=argparse.SUPPRESS)
    parser.add_argument("-l", "--local", action="store", type=dir_path, dest='local_path', help="define local data path")
    parser.add_argument("-r", "--remote", action="store", type=dir_path, dest='remote_path', help="define remote data path")
    parser.add_argument("-d", "--dry", action="store_true", dest='dry', help="do not remove local data after copying")
    return parser


def dir_path(directory: str) -> Path:
    """
    Convert a string to a Path object and check if the directory exists.

    This function is intended for use as a type conversion function with argparse.
    It takes a string argument representing a directory path, converts it into
    a Path object, and checks if the directory exists. If the directory exists,
    it returns the Path object; otherwise, it raises an argparse.ArgumentError
    with an appropriate error message.

    Parameters
    ----------
    directory : str
        A string representing a directory path.

    Returns
    -------
    pathlib.Path
        A Path object representing the directory.

    Raises
    ------
    argparse.ArgumentError
        If the directory does not exist, an argparse.ArgumentError is raised
        with an error message indicating that the directory was not found.
    """
    directory = Path(directory)
    if directory.exists():
        return directory
    raise argparse.ArgumentError(None, f'Directory `{directory}` not found')


def transfer_data_cli():
    """
    Command-line interface for transferring behavioral data to the local server.
    """
    args = _transfer_parser("Copy behavior data to the local server.").parse_args()
    transfer_data(**vars(args))


def transfer_video_data_cli():
    """
    Command-line interface for transferring video data to the local server.
    """
    args = _transfer_parser("Copy video data to the local server.").parse_args()
    transfer_video_data(**vars(args))


def transfer_ephys_data_cli():
    """
    Command-line interface for transferring ephys data to the local server.
    """
    args = _transfer_parser("Copy ephys data to the local server.").parse_args()
    transfer_ephys_data(**vars(args))


def _get_subjects_folders(local_path: Path, remote_path: Path) -> Tuple[Path, Path]:
    rig_paths = get_local_and_remote_paths(local_path, remote_path)
    local_path = rig_paths.local_subjects_folder
    remote_path = rig_paths.remote_subjects_folder
    assert isinstance(local_path, Path)
    if remote_path is None:
        raise Exception("Remote Path is not defined.")
    print(f'Local Path:  `{local_path}`')
    print(f'Remote Path: `{remote_path}`\n')
    return local_path, remote_path


def _get_session_paths(local_path: Path, glob_pattern: str = 'transfer_me.flag',
                       print_summary: bool = True) -> List[Path]:
    session_paths = [f.parent for f in local_path.rglob(glob_pattern)]
    if len(session_paths) == 0:
        print('Could not find any sessions to copy to the local server.')
        session_paths = list()
    elif print_summary:
        print('Going to copy following sessions to the local server:')
        for session_path in session_paths:
            print(f' * {session_path}')
        if input('Do you want to continue? [Y/n]  ') not in ('y', ''):
            session_paths = list()
    return session_paths


def transfer_ephys_data(local_path: Path = None, remote_path: Path = None, dry: bool = False):
    local_subject_folder, remote_subject_folder = _get_subjects_folders(local_path, remote_path)

    for session_path in _get_session_paths(local_subject_folder):
        vc = EphysCopier(session_path, remote_subjects_folder=remote_subject_folder)
        logger.critical(f"{vc.state}, {vc.session_path}")
        if not dry:
            vc.run()
    remove_local_sessions(weeks=2, local_path=local_subject_folder,
                          remote_path=remote_subject_folder, dry=dry, tag='ephys')


def transfer_video_data(local_path: Path = None, remote_path: Path = None, dry: bool = False):
    local_subject_folder, remote_subject_folder = _get_subjects_folders(local_path, remote_path)

    for session_path in _get_session_paths(local_subject_folder):
        vc = VideoCopier(session_path, remote_subjects_folder=remote_subject_folder)
        logger.critical(f"{vc.state}, {vc.session_path}")
        if not dry:
            vc.run()
    remove_local_sessions(weeks=2, local_path=local_subject_folder,
                          remote_path=remote_subject_folder, dry=dry, tag='video')


def transfer_data(local_path: Path = None, remote_path: Path = None, dry: bool = False, lab: str = None) -> None:
    """
    Copies the behavior data from the rig to the local server if the session has more than 42 trials
    If the hardware settings file contains MAIN_SYNC=True, the number of expected devices is set to 1
    :param local_path: local path to the subjects folder, otherwise uses the local_data_folder key in
    the iblrig_settings.yaml file, or the iblrig_data directory in the home path.

    Parameters
    ----------
    local_path : Path
        Path to local data
    remote_path : Path
        Path to remote data
    lab : str
        the lab name ie. "cortexlab" or "mainenlab" to use to find the local path. Defaults to the ALYX_LAB key
        in the settings/iblrig_settings.yaml file
    dry : bool
        Do not remove local data after copying if `dry` is True

    Returns
    -------
    None
    """
    local_subject_folder, remote_subject_folder = _get_subjects_folders(local_path, remote_path)
    hardware_settings = load_settings_yaml('hardware_settings.yaml')
    number_of_expected_devices = 1 if hardware_settings.get('MAIN_SYNC', True) else None

    for session_path in _get_session_paths(local_subject_folder):
        sc = BehaviorCopier(session_path, remote_subjects_folder=remote_subject_folder)
        task_settings = raw_data_loaders.load_settings(session_path, task_collection='raw_task_data_00')
        if task_settings is None:
            logger.info(f'skipping: no task settings found for {session_path}')
            continue
        # here if the session end time has not been labeled we assume that the session crashed, and patch the settings
        if task_settings['SESSION_END_TIME'] is None:
            jsonable = session_path.joinpath('raw_task_data_00', '_iblrig_taskData.raw.jsonable')
            if not jsonable.exists():
                logger.info(f'skipping: no task data found for {session_path}')
                if sc.remote_session_path.exists():
                    shutil.rmtree(sc.remote_session_path)
                continue
            trials, bpod_data = load_task_jsonable(jsonable)
            ntrials = trials.shape[0]
            # we have the case where the session hard crashed. Patch the settings file to wrap the session
            # and continue the copying
            logger.warning(f'recovering crashed session {session_path}')
            settings_file = session_path.joinpath('raw_task_data_00', '_iblrig_taskSettings.raw.json')
            with open(settings_file, 'r') as fid:
                raw_settings = json.load(fid)
            raw_settings['NTRIALS'] = int(ntrials)
            raw_settings['NTRIALS_CORRECT'] = int(trials['trial_correct'].sum())
            raw_settings['TOTAL_WATER_DELIVERED'] = int(trials['reward_amount'].sum())
            # cast the timestamp in a datetime object and add the session length to it
            end_time = datetime.datetime.strptime(raw_settings['SESSION_START_TIME'], '%Y-%m-%dT%H:%M:%S.%f')
            end_time += datetime.timedelta(seconds=bpod_data[-1]['Trial end timestamp'])
            raw_settings['SESSION_END_TIME'] = end_time.strftime('%Y-%m-%dT%H:%M:%S.%f')
            with open(settings_file, 'w') as fid:
                json.dump(raw_settings, fid)
            task_settings = raw_data_loaders.load_settings(session_path, task_collection='raw_task_data_00')
        # we check the number of trials acomplished. If the field is not there, we copy the session as is
        if task_settings.get('NTRIALS', 43) < 42:
            logger.info(f'Skipping: not enough trials for {session_path}')
            if sc.remote_session_path.exists():
                shutil.rmtree(sc.remote_session_path)
            continue
        logger.critical(f"{sc.state}, {sc.session_path}")
        sc.run(number_of_expected_devices=number_of_expected_devices)
    # once we copied the data, remove older session for which the data was successfully uploaded
    remove_local_sessions(weeks=2, dry=dry, local_path=local_subject_folder, remote_path=remote_subject_folder)


def remove_local_sessions(weeks=2, local_path=None, remote_path=None, dry=False, tag='behavior'):
    """
    Remove local sessions older than 2 weeks
    :param weeks:
    :param dry:
    :return:
    """
    local_subject_folder, remote_subject_folder = _get_subjects_folders(local_path, remote_path)
    size = 0
    match tag:
        case 'behavior': Copier = BehaviorCopier
        case 'video': Copier = VideoCopier
    for flag in sorted(list(local_subject_folder.rglob(f'_ibl_experiment.description_{tag}.yaml')), reverse=True):
        session_path = flag.parent
        days_elapsed = (datetime.datetime.now() - datetime.datetime.strptime(session_path.parts[-2], '%Y-%m-%d')).days
        if days_elapsed < (weeks * 7):
            continue
        sc = Copier(session_path, remote_subjects_folder=remote_subject_folder)
        if sc.state == 3:
            session_size = sum(f.stat().st_size for f in session_path.rglob('*') if f.is_file()) / 1024 ** 3
            logger.info(f"{sc.session_path}, {session_size:0.02f} Go")
            size += session_size
            if not dry:
                shutil.rmtree(session_path)
    logger.info(f"Cleanup size {size:0.02f} Go")


def viewsession():
    """
    Entry point for command line: usage as below
    >>> viewsession /full/path/to/jsonable/_iblrig_taskData.raw.jsonable
    :return: None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("file_jsonable", help="full file path to jsonable file")
    args = parser.parse_args()
    self = OnlinePlots()
    self.run(Path(args.file_jsonable))


def flush():
    """
    Flushes the valve until the user hits enter
    :return:
    """
    file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
    hardware_settings = yaml.safe_load(file_settings.read_text())
    bpod = Bpod(hardware_settings['device_bpod']['COM_BPOD'])
    bpod.flush()
    bpod.close()
