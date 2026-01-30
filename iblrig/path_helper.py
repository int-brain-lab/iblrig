import logging
import re
import shutil
from os import PathLike
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
import yaml
from packaging import version
from pydantic import ValidationError

from ibllib.io import session_params
from ibllib.io.raw_data_loaders import load_settings
from iblrig.constants import HARDWARE_SETTINGS_YAML, RIG_SETTINGS_YAML, SETTINGS_PATH
from iblrig.pydantic_definitions import BunchModel, HardwareSettings, RigSettings
from one.alf.spec import is_session_path

log = logging.getLogger(__name__)
T = TypeVar('T', HardwareSettings, RigSettings)


class SessionInfo(BunchModel):
    session_stub: str
    """Session stub in the form of YYYY-MM-DD_NNN"""
    session_path: Path
    """Path to the session folder"""
    task_collection: str
    """Name of the task collection"""
    experiment_description: dict
    """Experiment description"""
    task_settings: dict
    """Task settings"""
    file_task_data: Path
    """Path to the task data file"""


def iterate_previous_sessions(subject_name: str, task_name: str, n: int = 1, **kwargs) -> list[SessionInfo]:
    """
    Iterate over the sessions of a given subject in both the remote and local path and search for a given protocol name.
    Return the information of the last n found matching protocols in the form of a dictionary.

    Parameters
    ----------
    subject_name : str
        Name of the subject.
    task_name : str
        Name of the protocol to look for in experiment description.
    n : int, optional
        maximum number of protocols to return
    **kwargs
        Optional arguments to be passed to iblrig.path_helper.get_local_and_remote_paths
        If not used, will use the arguments from iblrig/settings/iblrig_settings.yaml

    Returns
    -------
    list[SessionInfo]
        List of SessionInfo
    """
    paths = get_local_and_remote_paths(**kwargs)
    sessions = _iterate_protocols(paths.local_subjects_folder / subject_name, task_name=task_name, n=n)
    if paths.remote_subjects_folder is not None:
        remote_sessions = _iterate_protocols(paths.remote_subjects_folder / subject_name, task_name=task_name, n=n)
        sessions.extend(remote_sessions)
        _, indices = np.unique([s.session_stub for s in sessions], return_index=True)  # returns *sorted* unique elements
        sessions = [sessions[i] for i in np.flipud(indices)]
    return sessions[:n]


def _iterate_protocols(subject_folder: PathLike | str, task_name: str, n: int = 1, min_trials: int = 43) -> list[SessionInfo]:
    """
    Return information on the last n sessions with matching protocol.

    This function iterates over the sessions of a given subject and searches for a given protocol name.

    Parameters
    ----------
    subject_folder : PathLike or str
        A subject folder containing dated folders.
    task_name : str
        The task protocol name to look for.
    n : int
        The number of previous protocols to return.
    min_trials : int
        Skips sessions with fewer than this number of trials.

    Returns
    -------
    list[SessionInfo]
        List of SessionInfo
    """

    def protocol_number(task_config: dict) -> int:
        """
        Return protocol number.

        Use `protocol_number` key if present (unlikely), otherwise use collection name.
        """
        if 'protocol_number' in task_config:
            return task_config['protocol_number']
        collection = task_config.get('collection', '')
        match = re.search(r'_(\d+)$', collection)
        return int(match.group(1)) if match else 0

    # return early if subject folder does not exist
    subject_folder = Path(subject_folder)
    if not subject_folder.exists():
        return []

    # list all sessions in subject folder
    sessions = list(subject_folder.glob('????-??-??/*/_ibl_experiment.description*.yaml'))  # seq may be X or XXX
    sessions = [x for x in sessions if is_session_path(x.parent.relative_to(subject_folder.parent))]

    protocols: list[SessionInfo] = []
    for file_experiment in sorted(sessions, reverse=True):
        session_path = file_experiment.parent
        experiment_description = session_params.read_params(file_experiment)

        # prefer the latest run if the same protocol ran more than once
        tasks = filter(None, map(lambda x: x.get(task_name), experiment_description.get('tasks', [])))
        for task in sorted(tasks, key=protocol_number, reverse=True):
            task_collection = task['collection']
            if not (task_settings := load_settings(session_path, task_collection=task_collection)):
                continue
            if task_settings.get('NTRIALS', min_trials + 1) < min_trials:  # ignore sessions with too few trials
                continue
            protocols.append(
                SessionInfo(
                    session_stub='_'.join(session_path.parts[-2:]),  # YYYY-MM-DD_NNN
                    session_path=session_path,
                    task_collection=task_collection,
                    experiment_description=experiment_description,
                    task_settings=task_settings,
                    file_task_data=session_path / task_collection / '_iblrig_taskData.raw.jsonable',
                )
            )
            if len(protocols) >= n:
                return protocols
    return protocols


class LocalAndRemotePaths(BunchModel):
    """Paths to local and remote data folders."""

    local_data_folder: Path
    remote_data_folder: Path | None
    local_subjects_folder: Path
    remote_subjects_folder: Path | None


def get_local_and_remote_paths(
    local_path: PathLike | str | None = None,
    remote_path: PathLike | str | None = None,
    lab: str | None = None,
    iblrig_settings: RigSettings | dict | None = None,
) -> LocalAndRemotePaths:
    """
    Parse input arguments to transfer commands.

    If the arguments are None, reads in the settings and returns the values from the files.
    ``local_subjects_path`` always has a fallback on the home directory / iblrig_data.
    ``remote_subjects_path`` has no fallback and will return None when all options are exhausted.

    Parameters
    ----------
    local_path : PathLike or str, optional
        Local data path. If None, the value is read from the settings file.
    remote_path : PathLike or str, optional
        Remote data path. If None, the value is read from the settings file.
    lab : str, optional
        Lab name used to construct the local subjects folder path. If None, the value is read from the settings file.
    iblrig_settings : RigSettings or dict, optional
        Settings dictionary. If None, the default settings files are loaded.

    Returns
    -------
    LocalAndRemotePaths
        Pydantic model with the following fields:

        - ``local_data_folder`` : pathlib.Path
        - ``remote_data_folder`` : pathlib.Path or None
        - ``local_subjects_folder`` : pathlib.Path
        - ``remote_subjects_folder`` : pathlib.Path or None
    """
    # we only want to attempt to load the settings file if necessary
    if iblrig_settings is None and ((local_path is None) or (remote_path is None) or (lab is None)):
        iblrig_settings = load_pydantic_yaml(RigSettings)

    # make sure that iblrig_settings is a dict
    # TODO: ideally we'd keep it as a Pydantic model throughout, but this may need refactoring some tests
    if isinstance(iblrig_settings, RigSettings):
        iblrig_settings = iblrig_settings.model_dump()
    elif iblrig_settings is None:
        iblrig_settings = {}

    # define local data folder
    local_data_folder = Path(local_path or iblrig_settings.get('iblrig_local_data_path', Path.home().joinpath('iblrig_data')))

    # define remote data folder
    remote_data_folder = remote_path or iblrig_settings.get('iblrig_remote_data_path')
    remote_data_folder = Path(remote_data_folder) if remote_data_folder else None

    # define local subjects folder
    local_subjects_folder = iblrig_settings.get('iblrig_local_subjects_path')
    if local_subjects_folder is None:
        if local_data_folder.name == 'Subjects':
            local_subjects_folder = local_data_folder
        elif (lab := lab or iblrig_settings.get('ALYX_LAB')) is not None:
            local_subjects_folder = local_data_folder / lab / 'Subjects'
        else:
            local_subjects_folder = local_data_folder / 'subjects'
            # NB: case is important here. ALF spec expects lab folder before 'Subjects' (capitalized)
    else:
        local_subjects_folder = Path(local_subjects_folder)

    # define remote subjects folder
    remote_subjects_folder = iblrig_settings.get('iblrig_remote_subjects_path')
    if remote_subjects_folder is None:
        if remote_data_folder is not None:
            if remote_data_folder.name == 'Subjects':
                remote_subjects_folder = remote_data_folder
            else:
                remote_subjects_folder = remote_data_folder / 'Subjects'
    else:
        remote_subjects_folder = Path(remote_subjects_folder)

    return LocalAndRemotePaths(
        local_data_folder=local_data_folder,
        remote_data_folder=remote_data_folder,
        local_subjects_folder=local_subjects_folder,
        remote_subjects_folder=remote_subjects_folder,
    )


def _load_settings_yaml(filename: PathLike | str = RIG_SETTINGS_YAML, do_raise: bool = True) -> dict[str, Any]:
    """
    Load and patch a YAML settings file.

    Parameters
    ----------
    filename : PathLike or str, optional
        Path to the YAML file. Bare filenames (without directory components)
        are resolved relative to the IBLRIG settings folder.
        Defaults to RIG_SETTINGS_YAML.
    do_raise : bool, optional
        If True (default), exceptions are raised. If False, exceptions are
        logged and an empty dict is returned.

    Returns
    -------
    dict[str, Any]
        The loaded and patched settings.
    """
    filename = Path(filename)

    # if the filename is relative, assume it is relative to the settings folder
    if filename.name == str(filename):
        filename = SETTINGS_PATH / filename

    # read the file and patch it, return as dict
    try:
        with filename.open() as f:
            settings_yaml = yaml.safe_load(f) or {}
        settings_yaml = patch_settings(settings_yaml, filename.stem)
    except Exception as e:
        if do_raise:
            raise
        else:
            log.exception(e)
            return {}
    return settings_yaml


def load_pydantic_yaml(model: type[T], filename: PathLike | str | None = None, do_raise: bool = True) -> T:
    """
    Load YAML data from a specified file or a standard IBLRIG settings file,
    validate it using a Pydantic model, and return the validated Pydantic model
    instance.

    Parameters
    ----------
    model : Type[T]
        The Pydantic model class to validate the YAML data against.
    filename : PathLike | str | None, optional
        The path to the YAML file.
        If None (default), the function deduces the appropriate standard IBLRIG
        settings file based on the model.
    do_raise : bool, optional
        If True (default), raise a ValidationError if validation fails.
        If False, log the validation error and construct a model instance
        with the provided data. Defaults to True.

    Returns
    -------
    T
        An instance of the Pydantic model, validated against the YAML data.

    Raises
    ------
    ValidationError
        If validation fails and do_raise is set to True.
        The raised exception contains details about the validation error.
    TypeError
        If the filename is None and the model class is not recognized as
        HardwareSettings or RigSettings.
    """
    if filename is None:
        if model == HardwareSettings:
            filename = HARDWARE_SETTINGS_YAML
        elif model == RigSettings:
            filename = RIG_SETTINGS_YAML
        else:
            raise TypeError(f'Cannot deduce filename for model `{model.__name__}`.')
    else:
        filename = Path(filename)

    # load and validate the settings file, return the validated model instance
    settings_dict = _load_settings_yaml(filename=filename, do_raise=True)

    if filename not in (HARDWARE_SETTINGS_YAML, RIG_SETTINGS_YAML):
        # TODO: We currently skip validation of pydantic models if an extra
        #       filename is provided that does NOT correspond to the standard
        #       settings files of IBLRIG. This should be re-evaluated.
        log.warning('Skipping validation of settings file `%s`', filename.name)
        do_raise = False
    try:
        return model.model_validate(settings_dict)
    except ValidationError as e:
        if not do_raise:
            log.exception(e)
            return model.model_construct(**settings_dict)
        else:
            raise


def save_pydantic_yaml(data: T, filename: PathLike | str | None = None) -> None:
    if filename is None:
        if isinstance(data, HardwareSettings):
            filename = HARDWARE_SETTINGS_YAML
        elif isinstance(data, RigSettings):
            filename = RIG_SETTINGS_YAML
        else:
            raise TypeError(f'Cannot deduce filename for model `{type(data).__name__}`.')
    else:
        filename = Path(filename)
    yaml_data = data.model_dump()
    data.model_validate(yaml_data)
    with filename.open('w') as f:
        log.debug(f'Dumping {type(data).__name__} to {filename.name}')
        yaml.dump(yaml_data, f, sort_keys=False)


def patch_settings(settings: dict, filename: str | PathLike) -> dict:
    """
    Update loaded settings files to ensure compatibility with latest version.

    Parameters
    ----------
    settings : dict
        A loaded settings file.
    filename : str | PathLike
        The filename of the settings file.

    Returns
    -------
    dict
        The updated settings.
    """
    filename = Path(filename)
    settings_version = version.parse(settings.get('VERSION', '0.0.0'))
    if filename.stem.startswith('hardware'):
        if settings_version < version.Version('1.0.0') and 'device_camera' in settings:
            log.info('Patching hardware settings; assuming left camera label')
            settings['device_cameras'] = {'left': settings.pop('device_camera')}
            settings['VERSION'] = '1.0.0'
        if 'device_cameras' in settings and settings['device_cameras'] is not None:
            settings['device_cameras'] = {k: v for k, v in settings['device_cameras'].items() if v}  # remove empty keys
            idx_missing = set(settings['device_cameras']) == {'left'} and 'INDEX' not in settings['device_cameras']['left']
            if settings_version < version.Version('1.1.0') and idx_missing:
                log.info('Patching hardware settings; assuming left camera index and training workflow')
                workflow = settings['device_cameras']['left'].pop('BONSAI_WORKFLOW', None)
                bonsai_workflows = {'setup': 'devices/camera_setup/setup_video.bonsai', 'recording': workflow}
                settings['device_cameras'] = {
                    'training': {'BONSAI_WORKFLOW': bonsai_workflows, 'left': {'INDEX': 1, 'SYNC_LABEL': 'audio'}}
                }
                settings['VERSION'] = '1.1.0'
        if settings.get('device_cameras') is None:
            settings['device_cameras'] = {}
    return settings


def iterate_collection(session_path: PathLike | str, collection_name='raw_task_data') -> str:
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
    session_path = Path(session_path)
    if not session_path.exists():
        return f'{collection_name}_00'
    tasks = sorted(p.name for p in session_path.glob(f'{collection_name}_[0-9][0-9]') if p.is_dir())
    if len(tasks) == 0:
        return f'{collection_name}_00'
    next_id = int(tasks[-1][-2:]) + 1
    if next_id > 99:
        raise ValueError(f'Maximum number of collections reached in {session_path}')
    return f'{collection_name}_{next_id:02}'


def create_bonsai_layout_from_template(workflow_file: Path) -> None:
    """
    Create a Bonsai layout file from a template if it does not already exist.

    If the file with the suffix `.bonsai.layout` does not exist for the given
    workflow file, this function will attempt to create it from a template
    file with the suffix `.bonsai.layout_template`. If the template file also
    does not exist, the function logs that no template layout is available.

    Background: Bonsai stores dialog settings (window position, control
    visibility, etc.) in an XML file with the suffix `.bonsai.layout`. These
    layout files are user-specific and may be overwritten locally by the user
    according to their preferences. To ensure that a default layout is
    available, a template file with the suffix `.bonsai.layout_template` can
    be provided as a starting point.

    Parameters
    ----------
    workflow_file : Path
        The path to the Bonsai workflow for which the layout is to be created.

    Raises
    ------
    FileNotFoundError
        If the provided workflow_file does not exist.
    """
    if not workflow_file.exists():
        raise FileNotFoundError(workflow_file)
    if not (layout_file := workflow_file.with_suffix('.bonsai.layout')).exists():
        template_file = workflow_file.with_suffix('.bonsai.layout_template')
        if template_file.exists():
            log.info(f'Creating default {layout_file.name}')
            shutil.copy(template_file, layout_file)
        else:
            log.debug(f'No template layout for {workflow_file.name}')
