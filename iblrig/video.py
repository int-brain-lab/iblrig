import argparse
import contextlib
import logging
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.error import URLError

import yaml
from iblutil.io import params
from iblutil.io import hashfile  # type: ignore
from iblutil.util import setup_logger
from one.webclient import AlyxClient, http_download_file  # type: ignore
from ibllib.pipes.misc import load_params_dict
from ibllib.io.video import get_video_meta, label_from_path
from ibllib.io.raw_data_loaders import load_embedded_frame_data

from iblrig.base_tasks import EmptySession
from iblrig.constants import HAS_PYSPIN, HAS_SPINNAKER, HARDWARE_SETTINGS_YAML, RIG_SETTINGS_YAML
from iblrig.tools import ask_user, call_bonsai
from iblrig.transfer_experiments import VideoCopier
from iblrig.path_helper import patch_settings

with contextlib.suppress(ImportError):
    from iblrig import video_pyspin

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def _download_from_alyx_or_flir(asset: int, filename: str, target_md5: str) -> Path:
    """
    Download a file from Alyx or FLIR server and verify its integrity using MD5 checksum.

    Parameters
    ----------
    asset : int
        The asset identifier for the file on FLIR server.
    filename : str
        The name of the file to be downloaded.
    target_md5 : str
        The expected MD5 checksum value for the downloaded file.

    Returns
    -------
    Path
        The path to the downloaded file.

    Raises
    ------
    Exception
        If the downloaded file's MD5 checksum does not match the expected value.
    """
    print(f'Downloading {filename} ...')
    out_dir = Path.home().joinpath('Downloads')
    out_file = out_dir.joinpath(filename)
    options = {'target_dir': out_dir, 'clobber': True, 'return_md5': True}
    if out_file.exists() and hashfile.md5(out_file) == target_md5:
        return out_file
    try:
        tmp_file, md5_sum = AlyxClient().download_file(f'resources/spinnaker/{filename}', **options)
    except (OSError, AttributeError, URLError) as e1:
        try:
            url = f'https://flir.netx.net/file/asset/{asset}/original/attachment'
            tmp_file, md5_sum = http_download_file(url, **options)
        except OSError as e2:
            raise e2 from e1
    os.rename(tmp_file, out_file)
    if md5_sum != target_md5:
        raise Exception(f'`{filename}` does not match the expected MD5 - please try running the script again or')
    return out_file


def install_spinnaker():
    """
    Install the Spinnaker SDK for Windows.

    Raises
    ------
    Exception
        If the function is not run on Windows.
    """

    # Check prerequisites
    if os.name != 'nt':
        raise Exception('install_spinnaker can only be run on Windows.')

    # Display some information
    print('This script will try to automatically download & install Spinnaker SDK for Windows')
    input('Press [ENTER] to continue.\n')

    # Check for existing installation
    if HAS_SPINNAKER and not ask_user('Spinnaker SDK for Windows is already installed. Do you want to continue anyways?'):
        return

    # Download & install Spinnaker SDK
    file_winsdk = _download_from_alyx_or_flir(54386, 'SpinnakerSDK_FULL_3.1.0.79_x64.exe', 'd9d83772f852e5369da2fbcc248c9c81')
    print('Installing Spinnaker SDK for Windows ...')
    input(
        'Please select the "Application Development" Installation Profile. Everything else can be left at '
        'default values. Press [ENTER] to continue.'
    )
    return_code = subprocess.check_call(file_winsdk)
    if return_code == 0:
        print('Installation of Spinnaker SDK was successful.')
    os.unlink(file_winsdk)


def install_pyspin():
    """
    Install PySpin to the IBLRIG Python environment.

    Raises
    ------
    Exception
        If the function is not run on Windows.
        If the function is not started in the IBLRIG virtual environment.
    """

    # Check prerequisites
    if os.name != 'nt':
        raise Exception('install_pyspin can only be run on Windows.')
    if sys.base_prefix == sys.prefix:
        raise Exception('install_pyspin needs to be started in the IBLRIG venv.')

    # Display some information
    print('This script will try to automatically download & install PySpin to the IBLRIG Python environment')
    input('Press [ENTER] to continue.\n')

    # Download & install PySpin
    if HAS_PYSPIN:
        print('PySpin is already installed.')
    else:
        file_zip = _download_from_alyx_or_flir(
            54396, 'spinnaker_python-3.1.0.79-cp310-cp310-win_amd64.zip', 'e00148800757d0ed7171348d850947ac'
        )
        print('Installing PySpin ...')
        with zipfile.ZipFile(file_zip, 'r') as f:
            file_whl = f.extract(file_zip.stem + '.whl', file_zip.parent)
        return_code = subprocess.check_call([sys.executable, '-m', 'pip', 'install', file_whl])
        if return_code == 0:
            print('Installation of PySpin was successful.')
        os.unlink(file_whl)
        file_zip.unlink()


def patch_old_params(remove_old=False, update_paths=True):
    """
    Update old video parameters.

    Parameters
    ----------
    remove_old : bool
        If true, removes the old video pc settings file.
    update_paths : bool
        If true, replace data paths in iblrig settings with those in old video pc settings file.

    """
    if not (old_file := Path(params.getfile('videopc_params'))).exists():
        return
    old_settings = load_params_dict('videopc_params')

    # Update hardware settings
    if HARDWARE_SETTINGS_YAML.exists():
        with open(HARDWARE_SETTINGS_YAML, 'r') as fp:
            hardware_settings = patch_settings(yaml.safe_load(fp), HARDWARE_SETTINGS_YAML)
    else:
        hardware_settings = {}
    cams = hardware_settings.get('device_cameras', {})
    for v in cams.values():
        for cam in filter(lambda k: k in v, ('left', 'right', 'body')):
            v[cam]['INDEX'] = old_settings.get(cam.upper() + '_CAM_IDX')

    # Save hardware settings
    hardware_settings['device_cameras'] = cams
    log.debug('Saving %s', HARDWARE_SETTINGS_YAML)
    with open(HARDWARE_SETTINGS_YAML, 'w') as fp:
        yaml.safe_dump(hardware_settings, fp)

    # Update other settings
    if update_paths:
        if RIG_SETTINGS_YAML.exists():
            with open(RIG_SETTINGS_YAML, 'r') as fp:
                rig_settings = yaml.safe_load(fp)
        else:
            rig_settings = {}
        path_map = {'iblrig_local_data_path': 'DATA_FOLDER_PATH',
                    'iblrig_remote_data_path': 'REMOTE_DATA_FOLDER_PATH'}
        for new_key, old_key in path_map.items():
            rig_settings[new_key] = old_settings[old_key].rstrip('\\')
            if rig_settings[new_key].endswith(r'\Subjects'):
                rig_settings[new_key] = rig_settings[new_key][:-len(r'\Subjects')]
            else:  # Add a 'subjects' key so that '\Subjects' is not incorrectly appended
                rig_settings[new_key.replace('data', 'subjects')] = rig_settings[new_key]
        log.debug('Saving %s', RIG_SETTINGS_YAML)
        with open(RIG_SETTINGS_YAML, 'w') as fp:
            yaml.safe_dump(rig_settings, fp)

    if remove_old:
        # Deleting old file
        log.info('Removing %s', old_file)
        old_file.unlink()


def prepare_video_session_cmd():
    if not HAS_SPINNAKER:
        if ask_user("Spinnaker SDK doesn't seem to be installed. Do you want to install it now?"):
            install_spinnaker()
        return
    if not HAS_PYSPIN:
        if ask_user("PySpin doesn't seem to be installed. Do you want to install it now?"):
            install_pyspin()
        return

    parser = argparse.ArgumentParser(prog='start_video_session', description='Prepare video PC for video recording session.')
    parser.add_argument('subject_name', help='name of subject')
    parser.add_argument('profile', help='camera configuration name, found in "device_cameras" map of hardware_settings.yaml')
    parser.add_argument('--debug', action='store_true', help='enable debugging mode')
    args = parser.parse_args()
    setup_logger(name='iblrig', level=10 if args.debug else 20)
    prepare_video_session(args.subject_name, args.profile, debug=args.debug)


def validate_video(video_path, config):
    """
    Check raw video file saved as expected.

    Parameters
    ----------
    video_path : pathlib.Path
        Path to the video file.
    config : iblrig.pydantic_definitions.HardwareSettingsCamera
        The expected video configuration.

    Returns
    -------
    bool
        True if all checks pass.
    """
    if not video_path.exists():
        log.critical('Raw video file does not exist: %s', video_path)
        return False
    elif video_path.stat().st_size == 0:
        log.critical('Raw video file empty: %s', video_path)
        return False
    try:
        meta = get_video_meta(video_path)
        ok = meta.length > 0 and meta.duration > 0
        log.log(20 if meta.length > 0 else 40, 'N frames = %i', meta.length)
        log.log(20 if meta.duration > 0 else 40, 'Duration = %.2f', meta.duration)
        if config.HEIGHT and config.HEIGHT != meta.height:
            ok = False
            log.warning('Frame height = %i; expected %i', config.HEIGHT, meta.height)
        if config.WIDTH and config.WIDTH != meta.width:
            log.warning('Frame width = %i; expected %i', config.WIDTH, meta.width)
            ok = False
        if config.FPS and config.FPS != meta.fps:
            log.warning('Frame rate = %i; expected %i', config.FPS, meta.fps)
            ok = False
    except AssertionError:
        log.critical('Failed to open video file: %s', video_path)
        return False

    # Check frame data
    count, gpio = load_embedded_frame_data(video_path.parents[1], label_from_path(video_path))
    if count[-1] != meta.length - 1:
        log.error('Frame count / video frame mismatch - frame counts = %i; video frames = %i', count[-1], meta.length)
        ok = False
    if len(count) != meta.length:
        log.warning('Missed frames - frame data N = %i; video file N = %i', count[-1], meta.length)
        ok = False
    if config.SYNC_LABEL:
        MIN_EVENTS = 10  # The minimum expected number of GPIO events
        if all(ch is None for ch in gpio):
            log.error('No GPIO events detected.')
            ok = False
        else:
            for i, ch in enumerate(gpio):
                if ch:
                    log.log(30 if len(ch['indices']) < MIN_EVENTS else 20, '%i event(s) on GPIO #%i', len(ch['indices']), i + 1)
    return ok


def prepare_video_session(subject_name: str, config_name: str, debug: bool = False):
    """
    Setup and record video.

    Parameters
    ----------
    subject_name : str
        A subject name.
    config_name : str
        Camera configuration name, found in "device_cameras" map of hardware_settings.yaml.
    debug : bool
        Bonsai debug mode and verbose logging.
    """
    assert HAS_SPINNAKER
    assert HAS_PYSPIN

    # Initialize a session for paths and settings
    session = EmptySession(subject=subject_name, interactive=False)
    session_path = session.paths.SESSION_FOLDER
    raw_data_folder = session_path.joinpath('raw_video_data')

    # Fetch camera configuration from hardware settings file
    try:
        config = session.hardware_settings.device_cameras[config_name]
    except AttributeError as ex:
        if hasattr(value_error := ValueError('"No camera config in hardware_settings.yaml file."'), 'add_note'):
            value_error.add_note(HARDWARE_SETTINGS_YAML)  # py 3.11
        raise value_error from ex
    except KeyError as ex:
        raise ValueError(f'Config "{config_name}" not in "device_cameras" hardware settings.') from ex
    workflows = config.pop('BONSAI_WORKFLOW')
    cameras = [k for k in config if k != 'BONSAI_WORKFLOW']
    params = {f'{k}CameraIndex': config[k].INDEX for k in cameras}
    raw_data_folder.mkdir(parents=True, exist_ok=True)

    # align cameras
    if workflows.setup:
        video_pyspin.enable_camera_trigger(enable=False)
        call_bonsai(workflows.setup, params, debug=debug)

    # record video
    filenamevideo = '_iblrig_{}Camera.raw.avi'
    filenameframedata = '_iblrig_{}Camera.frameData.bin'
    for k in map(str.capitalize, cameras):
        params[f'FileName{k}'] = str(raw_data_folder / filenamevideo.format(k.lower()))
        params[f'FileName{k}Data'] = str(raw_data_folder / filenameframedata.format(k.lower()))
    video_pyspin.enable_camera_trigger(enable=True)
    bonsai_process = call_bonsai(workflows.recording, params, wait=False, debug=debug)
    input('PRESS ENTER TO START CAMERAS')
    # Save the stub files locally and in the remote repo for future copy script to use
    copier = VideoCopier(session_path=session_path, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
    copier.initialize_experiment(acquisition_description=copier.config2stub(config, raw_data_folder.name))

    video_pyspin.enable_camera_trigger(enable=False)
    log.info('To terminate video acquisition, please stop and close Bonsai workflow.')
    bonsai_process.wait()
    log.info('Video acquisition session finished.')

    # Check video files were saved and configured correctly
    for video_file in (Path(v) for v in params.values() if isinstance(v, str) and v.endswith('.avi')):
        validate_video(video_file, config[label_from_path(video_file)])

    session_path.joinpath('transfer_me.flag').touch()
    # remove empty-folders and parent-folders
    if not any(raw_data_folder.iterdir()):
        os.removedirs(raw_data_folder)
