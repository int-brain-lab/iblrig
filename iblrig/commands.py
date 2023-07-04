import argparse
from pathlib import Path

from deploy.transfer_data import transfer_sessions
from iblutil.util import setup_logger

from iblrig.path_helper import load_settings_yaml, get_iblrig_path
from iblrig.online_plots import OnlinePlots

logger = setup_logger('iblrig', level='INFO')


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


def transfer_data():
    """
    >>> transfer_data -l /full/path/to/iblrig_data/Subjects -r /full/path/to/remote/folder/Subjects
    :return:
    """
    help_str = ">>> transfer_data -l /full/path/to/iblrig_data/Subjects -r /full/path/to/remote/folder/Subjects"

    iblrig_settings = load_settings_yaml()
    default_local = iblrig_settings['iblrig_local_data_path']
    default_remote = iblrig_settings['iblrig_remote_data_path']

    parser = argparse.ArgumentParser(description='Transfers data from the rigs to the local server',
                                     epilog=help_str)
    parser.add_argument('-l', '--local', default=default_local, required=False, help='Local iblrig_data/Subjects folder')
    parser.add_argument('-r', '--remote', default=default_remote, required=False, help='Remote iblrig_data/Subjects folder')
    args = parser.parse_args()

    error_message = (f'path should be specified in settings files here: \n'
                     f'         {get_iblrig_path().joinpath("settings", "iblrig_settings.yaml")} \n '
                     f'                         OR through command line as shown here: \n'
                     f'         {help_str}')

    if args.local is None:
        logger.critical('Local ' + error_message)
        return

    if args.remote is None:
        logger.critical('Remote ' + error_message)
        return

    remote = Path(args.remote)
    local = Path(args.local)
    logger.info(f'Transfering data from {local} to {remote}')

    if not remote.exists():
        logger.critical(f'Remote path does not exist: {args.remote} \n {help_str}')
        return

    if not remote.exists():
        logger.critical(f'Local path does not exist: {args.remote} \n {help_str}')
        return

    transfer_sessions(local, remote)
