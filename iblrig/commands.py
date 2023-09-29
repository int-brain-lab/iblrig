import argparse
import datetime
import json
from pathlib import Path
import yaml
import shutil

from iblutil.util import setup_logger
from ibllib.io import raw_data_loaders
from iblrig.transfer_experiments import BehaviorCopier, VideoCopier
import iblrig
from iblrig.hardware import Bpod
from iblrig.path_helper import load_settings_yaml, get_local_and_remote_paths
from iblrig.online_plots import OnlinePlots
from iblrig.raw_data_loaders import load_task_jsonable

logger = setup_logger('iblrig', level='INFO')


def transfer_video_data(local_subjects_path=None, remote_subjects_path=None, dry=False):
    local_subjects_path, remote_subjects_path = get_local_and_remote_paths(
        local_path=local_subjects_path, remote_path=remote_subjects_path)

    for flag in list(local_subjects_path.rglob('transfer_me.flag')):
        session_path = flag.parent
        vc = VideoCopier(session_path, remote_subjects_folder=remote_subjects_path)
        logger.critical(f"{vc.state}, {vc.session_path}")
        if not dry:
            vc.run()
    remove_local_sessions(weeks=2, local_subjects_path=local_subjects_path,
                          remote_subjects_path=remote_subjects_path, dry=dry, tag='video')


def transfer_data(local_path=None, remote_path=None, dry=False):
    """
    Copies the behavior data from the rig to the local server if the session has more than 42 trials
    If the hardware settings file contains MAIN_SYNC=True, the number of expected devices is set to 1
    :param local_path: local path to the subjects folder, otherwise uses the local_data_folder key in
    the iblrig_settings.yaml file, or the iblrig_data directory in the home path.
    :param dry:
    :return:
    """
    # If paths not passed, uses those defined in the iblrig_settings.yaml file
    rig_paths = get_local_and_remote_paths(local_path=local_path, remote_path=remote_path)
    local_path = rig_paths.local_subjects_folder
    remote_path = rig_paths.remote_subjects_folder
    assert isinstance(local_path, Path)  # get_local_and_remote_paths should always return Path obj

    hardware_settings = load_settings_yaml('hardware_settings.yaml')
    number_of_expected_devices = 1 if hardware_settings.get('MAIN_SYNC', True) else None

    for flag in list(local_path.rglob('transfer_me.flag')):
        session_path = flag.parent
        sc = BehaviorCopier(session_path, remote_subjects_folder=rig_paths['remote_subjects_folder'])
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
    remove_local_sessions(weeks=2, dry=dry, local_path=local_path, remote_path=remote_path)


def remove_local_sessions(weeks=2, local_path=None, remote_path=None, dry=False, tag='behavior'):
    """
    Remove local sessions older than 2 weeks
    :param weeks:
    :param dry:
    :return:
    """
    rig_paths = get_local_and_remote_paths(local_path=local_path, remote_path=remote_path)
    size = 0
    match tag:
        case 'behavior': Copier = BehaviorCopier
        case 'video': Copier = VideoCopier
    for flag in sorted(list(rig_paths['local_subjects_folder'].rglob(f'_ibl_experiment.description_{tag}.yaml')), reverse=True):
        session_path = flag.parent
        days_elapsed = (datetime.datetime.now() - datetime.datetime.strptime(session_path.parts[-2], '%Y-%m-%d')).days
        if days_elapsed < (weeks * 7):
            continue
        sc = Copier(session_path, remote_subjects_folder=rig_paths['remote_subjects_folder'])
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
