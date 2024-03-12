import argparse
import datetime
import logging
import shutil
import warnings
from collections.abc import Iterable
from pathlib import Path

import yaml

import iblrig
from iblrig.hardware import Bpod
from iblrig.online_plots import OnlinePlots
from iblrig.path_helper import get_local_and_remote_paths
from iblrig.transfer_experiments import BehaviorCopier, EphysCopier, SessionCopier, VideoCopier
from iblutil.util import setup_logger

logger = logging.getLogger(__name__)


tag2copier = {'behavior': BehaviorCopier, 'video': VideoCopier, 'ephys': EphysCopier}


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
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter, argument_default=argparse.SUPPRESS
    )
    parser.add_argument('--tag', default='behavior', type=str, help='data type to transfer, e.g. "behavior", "video"')
    parser.add_argument('-l', '--local', action='store', type=dir_path, dest='local_path', help='define local data path')
    parser.add_argument('-r', '--remote', action='store', type=dir_path, dest='remote_path', help='define remote data path')
    parser.add_argument('-d', '--dry', action='store_true', dest='dry', help='do not remove local data after copying')
    parser.add_argument(
        '--cleanup-weeks', type=int, help='cleanup data older than this many weeks (-1 for no cleanup)', default=2
    )
    parser.add_argument(
        '--subject', type=str, help='an optional subject name to filter sessions by. Wildcards accepted.', default='*'
    )
    parser.add_argument(
        '--date', type=str, help='an optional date pattern to filter sessions by. Wildcards accepted.', default='*-*-*'
    )
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
    setup_logger('iblrig', level='INFO')
    args = _transfer_parser('Copy data to the local server.').parse_args()
    transfer_data(**vars(args), interactive=True)


def transfer_video_data_cli():
    """
    Command-line interface for transferring video data to the local server.
    """
    setup_logger('iblrig', level='INFO')
    warnings.warn('transfer_video_data will be removed in the future. Use "transfer_data video" instead.', FutureWarning)
    args = _transfer_parser('Copy video data to the local server.').parse_args()
    transfer_data(**{**vars(args), 'tag': 'video'}, interactive=True)


def transfer_ephys_data_cli():
    """
    Command-line interface for transferring ephys data to the local server.
    """
    setup_logger('iblrig', level='INFO')
    warnings.warn('transfer_ephys_data will be removed in the future. Use "transfer_data ephys" instead.', FutureWarning)
    args = _transfer_parser('Copy ephys data to the local server.').parse_args()
    transfer_data(**{**vars(args), 'tag': 'ephys'}, interactive=True)


def _get_subjects_folders(local_path: Path, remote_path: Path) -> tuple[Path, Path]:
    rig_paths = get_local_and_remote_paths(local_path, remote_path)
    local_path = rig_paths.local_subjects_folder
    remote_path = rig_paths.remote_subjects_folder
    assert isinstance(local_path, Path)
    if remote_path is None:
        raise Exception('Remote Path is not defined.')
    return local_path, remote_path


def _get_copiers(
    copier: type[SessionCopier],
    local_folder: Path,
    remote_folder: Path,
    lab: str = None,
    glob_pattern: str = '*/????-??-??/*/transfer_me.flag',
    interactive: bool = False,
    **kwargs,
) -> list[SessionCopier]:
    """

    Parameters
    ----------
    copier : SessionCopier
        A SessionCopier class to instantiate for each session.
    local_folder : str
        The absolute path of the local data directory (the copy root source). If None, loads from
        the iblrig settings file.
    remote_folder : str
        The absolute path of the remote data directory (the copy root destination). If None, loads
        from the iblrig settings file.
    lab : str
        The name of the lab. Only used if 'iblrig_local_subjects_path' is not defined in the
        settings file. If None, uses 'ALYX_LAB' field of iblrig settings.
    glob_pattern : str
        The filename to recursively search within `local_folder` for determining which sessions to
        copy.
    interactive : bool
        If true, users are prompted to review the sessions to copy before proceeding.
    kwargs
        Extract arguments such as `tag` to pass to the SessionCopier.

    Returns
    -------
    list of SessionCopier
        A list of SessionCopier objects.
    """
    # get local/remote subjects folder
    rig_paths = get_local_and_remote_paths(local_path=local_folder, remote_path=remote_folder, lab=lab)
    local_subjects_folder = local_folder or rig_paths.local_subjects_folder
    remote_subjects_folder = remote_folder or rig_paths.remote_subjects_folder
    assert isinstance(local_subjects_folder, Path)
    if remote_subjects_folder is None:
        raise Exception('Remote Path is not defined.')
    level = logging.INFO if interactive else logging.DEBUG
    logger.log(level, 'Local Path: %s', local_subjects_folder)
    logger.log(level, 'Remote Path: %s', remote_subjects_folder)

    # get copiers
    copiers = [copier(f.parent, remote_subjects_folder, **kwargs) for f in local_subjects_folder.glob(glob_pattern)]
    if len(copiers) == 0:
        print('Could not find any sessions to copy to the local server.')
    elif interactive:
        _print_status(copiers, 'Session states prior to transfer operation:')
        if input('\nDo you want to continue? [Y/n]  ').lower() not in ('y', ''):
            copiers = []
    return copiers


def _print_status(copiers: Iterable[SessionCopier], heading: str = '') -> None:
    print(heading)
    for copier in copiers:
        match copier.state:
            case 0:
                state = 'not registered on server'
            case 1:
                state = 'copy pending'
            case 2:
                state = 'copy complete'
            case 3:
                state = 'copy finalized'
            case _:
                state = 'undefined'
        print(f' * {copier.session_path}: {state}')


def _build_glob_pattern(subject='*', date='*-*-*', number='*', flag_file='transfer_me.flag', **kwargs):
    """
    Build the copier glob pattern from filter keyword arguments.

    Parameters
    ----------
    subject : str
        A subject folder filter pattern.
    date : str
        A date folder pattern.
    number : str
        A number (i.e. experiment sequence) folder pattern.
    flag_file : str
        A flag filename pattern.
    glob_pattern : str
        The full glob pattern string (if defined, overrides all other arguments).

    Returns
    -------
    str
        The full glob pattern.
    """
    return kwargs.get('glob_pattern', '/'.join((subject, date, number, flag_file)))


def transfer_data(
    tag=None,
    local_path: Path = None,
    remote_path: Path = None,
    dry: bool = False,
    interactive: bool = False,
    cleanup_weeks=2,
    **kwargs,
) -> list[SessionCopier]:
    """
    Copies data from the rig to the local server.

    Parameters
    ----------
    tag : str
        The acquisition PC tag to transfer, e.g. 'behavior', 'video', 'ephys', 'timeline', etc.
    local_path : Path
        Path to local subjects folder, otherwise fetches path from iblrig_settings.yaml file.
    remote_path : Path
        Path to remote subjects folder, otherwise fetches path from iblrig_settings.yaml file.
    dry : bool
        Do not copy or remove local data.
    interactive : bool
        If true, users are prompted to review the sessions to copy before proceeding.
    cleanup_weeks : int, bool
        Remove local data older than this number of weeks. If False, do not remove.
    kwargs
        Optional arguments to pass to SessionCopier constructor.

    Returns
    -------
    list of SessionCopier
        A list of the copier objects that were run.
    """
    if not tag:
        raise ValueError('Tag required.')
    # Build glob patten based on subject/date/number/flag_file filter
    kwargs['glob_pattern'] = _build_glob_pattern(**kwargs)
    kwargs = {k: v for k, v in kwargs.items() if k not in ('subject', 'date', 'number', 'flag_file')}
    local_subject_folder, remote_subject_folder = _get_subjects_folders(local_path, remote_path)
    copier = tag2copier.get(tag.lower(), SessionCopier)
    logger.info('Searching for %s sessions using %s class', tag.lower(), copier.__name__)
    expected_devices = kwargs.pop('number_of_expected_devices', None)
    copiers = _get_copiers(copier, local_subject_folder, remote_subject_folder, interactive=interactive, tag=tag, **kwargs)

    for copier in copiers:
        logger.critical(f'{copier.state}, {copier.session_path}')
        if not dry:
            copier.run(number_of_expected_devices=expected_devices)

    if interactive:
        _print_status(copiers, 'States after transfer operation:')

    # once we copied the data, remove older session for which the data was successfully uploaded
    if isinstance(cleanup_weeks, int) and cleanup_weeks > -1:
        remove_local_sessions(
            weeks=cleanup_weeks, dry=dry, local_path=local_subject_folder, remote_path=remote_subject_folder, tag=tag
        )
    return copiers


def remove_local_sessions(weeks=2, local_path=None, remote_path=None, dry=False, tag='behavior'):
    """
    Remove local sessions older than N weeks.

    Parameters
    ----------
    weeks : int
        Remove local sessions older than this number of weeks.
    local_path : Path
        Path to local subjects folder, otherwise fetches path from iblrig_settings.yaml file.
    remote_path : Path
        Path to remote subjects folder, otherwise fetches path from iblrig_settings.yaml file.
    dry : bool
        Do not remove local data if True.
    tag : str
        The acquisition PC tag to transfer, e.g. 'behavior', 'video', 'ephys', 'timeline', etc.

    Returns
    -------
    list of Path
        A list of removed session paths.
    """
    local_subject_folder, remote_subject_folder = _get_subjects_folders(local_path, remote_path)
    size = 0
    Copier = tag2copier.get(tag.lower(), SessionCopier)
    removed = []
    for flag in sorted(list(local_subject_folder.rglob(f'_ibl_experiment.description_{tag}.yaml')), reverse=True):
        session_path = flag.parent
        days_elapsed = (datetime.datetime.now() - datetime.datetime.strptime(session_path.parts[-2], '%Y-%m-%d')).days
        if days_elapsed < (weeks * 7):
            continue
        sc = Copier(session_path, remote_subjects_folder=remote_subject_folder)
        if sc.state == 3:
            session_size = sum(f.stat().st_size for f in session_path.rglob('*') if f.is_file()) / 1024**3
            logger.info(f'{sc.session_path}, {session_size:0.02f} Go')
            size += session_size
            if not dry:
                shutil.rmtree(session_path)
            removed.append(session_path)
    logger.info(f'Cleanup size {size:0.02f} Go')
    return removed


def viewsession():
    """
    Entry point for command line: usage as below
    >>> viewsession /full/path/to/jsonable/_iblrig_taskData.raw.jsonable
    :return: None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('file_jsonable', help='full file path to jsonable file')
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
