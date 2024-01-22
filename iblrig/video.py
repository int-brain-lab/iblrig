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
from one.webclient import AlyxClient, http_download_file  # type: ignore
from ibllib.pipes.misc import load_params_dict

from iblrig.base_tasks import EmptySession
from iblrig.constants import BASE_PATH, HAS_PYSPIN, HAS_SPINNAKER, HARDWARE_SETTINGS_YAML, RIG_SETTINGS_YAML
from iblrig.tools import ask_user, call_bonsai
from iblrig.transfer_experiments import VideoCopier

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
            hardware_settings = yaml.safe_load(fp)
    else:
        hardware_settings = {}
    cams = hardware_settings.get('device_cameras', {})
    for cam in ('left', 'right', 'body'):
        cams[cam] = {**cams.get(cam, {}), **{'INDEX': old_settings.get(cam.upper() + '_CAM_IDX')}}

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


def create_videopc_params(force=False, silent=False):
    from iblutil.io import params
    from ibllib.pipes.misc import cli_ask_default

    if Path(params.getfile('videopc_params')).exists() and not force:
        print(f'{params.getfile("videopc_params")} exists already, exiting...')
        print(Path(params.getfile('videopc_params')).exists())
        return
    if silent:
        data_folder_path = r'D:\iblrig_data\Subjects'
        remote_data_folder_path = r'\\iblserver.champalimaud.pt\ibldata\Subjects'
        body_cam_idx = 0
        left_cam_idx = 1
        right_cam_idx = 2
    else:
        data_folder_path = cli_ask_default(
            r'Where\'s your LOCAL "Subjects" data folder?', r'D:\iblrig_data\Subjects'
        )
        remote_data_folder_path = cli_ask_default(
            r'Where\'s your REMOTE "Subjects" data folder?',
            r'\\iblserver.champalimaud.pt\ibldata\Subjects',
        )
        body_cam_idx = cli_ask_default('Please select the index of the BODY camera', '0')
        left_cam_idx = cli_ask_default('Please select the index of the LEFT camera', '1')
        right_cam_idx = cli_ask_default("Please select the index of the RIGHT camera", '2')

    param_dict = {
        'DATA_FOLDER_PATH': data_folder_path,
        'REMOTE_DATA_FOLDER_PATH': remote_data_folder_path,
        'BODY_CAM_IDX': body_cam_idx,
        'LEFT_CAM_IDX': left_cam_idx,
        'RIGHT_CAM_IDX': right_cam_idx,
    }
    params.write('videopc_params', param_dict)
    print(f'Created {params.getfile("videopc_params")}')
    print(param_dict)
    return param_dict


def prepare_video_session_cmd():
    if not HAS_SPINNAKER:
        if ask_user("Spinnaker SDK doesn't seem to be installed. Do you want to install it now?"):
            install_spinnaker()
        return
    if not HAS_PYSPIN:
        if ask_user("PySpin doesn't seem to be installed. Do you want to install it now?"):
            install_pyspin()
        return

    parser = argparse.ArgumentParser(prog='start_video_session', description='Prepare video PC for video recording session')
    parser.add_argument('subject_name', help='name of subject')
    parser.add_argument('-t', '--training', action='store_true', help='launch video workflow for training session')
    args = parser.parse_args()

    prepare_video_session(args.subject_name, training_session=args.training)


def prepare_video_session(subject_name: str, training_session: bool = False):
    assert HAS_SPINNAKER
    assert HAS_PYSPIN

    session = EmptySession(subject=subject_name, interactive=False)
    session_folder = session.paths.SESSION_FOLDER
    raw_data_folder = session_folder.joinpath('raw_video_data')
    raw_data_folder.mkdir(parents=True, exist_ok=True)
    cam_index = {'Body': 0, 'Left': 1, 'Right': 2}

    # align cameras
    bonsai_workflow = BASE_PATH.joinpath('devices', 'camera_setup', 'EphysRig_SetupCameras.bonsai')
    params = {}
    for key, value in cam_index.items():
        params[f'{key}CameraIndex'] = value
    video_pyspin.enable_camera_trigger(enable=False)
    call_bonsai(bonsai_workflow, params)

    # record video
    if training_session:
        bonsai_workflow = BASE_PATH.joinpath('devices', 'camera_recordings', 'EphysRig_SaveVideo_TrainingTasks.bonsai')
    else:
        bonsai_workflow = BASE_PATH.joinpath('devices', 'camera_recordings', 'EphysRig_SaveVideo_EphysTasks.bonsai')
    for key, _ in cam_index.items():
        params[f'FileName{key}'] = raw_data_folder.joinpath(f'_iblrig_{key.lower()}Camera.raw.avi')
        params[f'FileName{key}Data'] = raw_data_folder.joinpath(f'_iblrig_{key.lower()}Camera.frameData.bin')
    video_pyspin.enable_camera_trigger(enable=True)
    bonsai_process = call_bonsai(bonsai_workflow, params, wait=False)
    input('PRESS ENTER TO START CAMERAS')
    video_pyspin.enable_camera_trigger(enable=False)
    vc = VideoCopier(session_path=session_folder)
    vc.create_video_stub(nvideos=1 if training_session else 3)
    session_folder.joinpath('transfer_me.flag').touch()
    bonsai_process.wait()

    # remove empty-folders and parent-folders
    if not any(raw_data_folder.iterdir()):
        os.removedirs(raw_data_folder)
