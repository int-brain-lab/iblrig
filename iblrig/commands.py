import argparse
import datetime
from pathlib import Path
import yaml
import shutil

from iblutil.util import setup_logger
from ibllib.io import raw_data_loaders, session_params
from iblrig.transfer_experiments import SessionCopier
import iblrig
from iblrig.hardware import Bpod
from iblrig.path_helper import load_settings_yaml
from iblrig.online_plots import OnlinePlots

logger = setup_logger('iblrig', level='INFO')


def transfer_data():
    """
    Remove local sessions older than 2 weeks
    :param weeks:
    :param dry:
    :return:
    """
    iblrig_settings = load_settings_yaml()
    local_subjects_path = Path(iblrig_settings['iblrig_local_data_path'])
    remote_subjects_path = Path(iblrig_settings['iblrig_remote_data_path']).joinpath('Subjects')

    for flag in list(local_subjects_path.rglob('transfer_me.flag')):
        session_path = flag.parent
        task_settings = raw_data_loaders.load_settings(session_path, task_collection='raw_task_data_00')
        if task_settings is None or task_settings['NTRIALS'] < 42:
            print('Skipping {}'.format(session_path))
            continue
        sc = SessionCopier(session_path, remote_subjects_folder=remote_subjects_path)
        state = sc.get_state()
        logger.critical(f"{sc.state}, {sc.session_path}")
        # session_params.write_yaml(sc.file_remote_experiment_description, ad)
        if sc.state == -1:  # this case is not implemented automatically and corresponds to a hard reset
            logger.info(f"{sc.state}, {sc.session_path}")
            shutil.rmtree(sc.remote_session_path)
            sc.initialize_experiment(session_params.read_params(session_path))
        if sc.state == 0:  # the session hasn't even been initialzed: copy the stub to the remote
            logger.info(f"{sc.state}, {sc.session_path}")
            state = sc.initialize_experiment(session_params.read_params(session_path))
        if sc.state == 1:  # the session
            logger.info(f"{sc.state}, {sc.session_path}")
            state = sc.copy_collections()
        if sc.state == 2:
            logger.info(f"{sc.state}, {sc.session_path}")
            state = sc.finalize_copy(number_of_expected_devices=1)
        if sc.state == 3:
            logger.info(f"{state}, {sc.session_path}")


def remove_local_sessions(weeks=2, dry=False):
    """
    Remove local sessions older than 2 weeks
    :param weeks:
    :param dry:
    :return:
    """
    iblrig_settings = load_settings_yaml()
    local_subjects_path = Path(iblrig_settings['iblrig_local_data_path'])
    remote_subjects_path = Path(iblrig_settings['iblrig_remote_data_path']).joinpath('Subjects')

    size = 0
    for flag in sorted(list(local_subjects_path.rglob('_ibl_experiment.description_behavior.yaml')), reverse=True):
        session_path = flag.parent
        age = (datetime.datetime.now() - datetime.datetime.strptime(session_path.parts[-2], '%Y-%m-%d')).days
        if age < weeks * 7:
            continue
        sc = SessionCopier(session_path, remote_subjects_folder=remote_subjects_path)
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
