import argparse
import asyncio
import contextlib
import logging
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

from ibllib.io.raw_data_loaders import load_embedded_frame_data
from ibllib.io.video import get_video_meta, label_from_path
from ibllib.pipes.misc import load_params_dict
from iblrig.base_tasks import EmptySession
from iblrig.constants import HARDWARE_SETTINGS_YAML, HAS_PYSPIN, HAS_SPINNAKER, RIG_SETTINGS_YAML
from iblrig.net import ExpInfo, get_server_communicator, read_stdin, update_alyx_token
from iblrig.path_helper import load_pydantic_yaml, patch_settings
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.tools import ask_user, call_bonsai, call_bonsai_async
from iblrig.transfer_experiments import VideoCopier
from iblutil.io import (
    hashfile,  # type: ignore
    net,
    params,
)
from iblutil.util import setup_logger
from one.api import OneAlyx
from one.converters import ConversionMixin
from one.remote import aws
from one.webclient import http_download_file  # type: ignore

with contextlib.suppress(ImportError):
    from iblrig import video_pyspin

SPINNAKER_ASSET = 59586
SPINNAKER_FILENAME = 'SpinnakerSDK_FULL_3.2.0.57_x64.exe'
SPINNAKER_MD5 = 'aafc07c858dc2ab2e2a7d6ef900ca9a7'

PYSPIN_ASSET = 59584
PYSPIN_FILENAME = 'spinnaker_python-3.2.0.57-cp310-cp310-win_amd64.zip'
PYSPIN_MD5 = 'f93294208e0ecec042adb2f75cb72609'

log = logging.getLogger(__name__)


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

    # if the file already exists skip all downloads
    if out_file.exists() and hashfile.md5(out_file) == target_md5:
        return out_file

    # first try to download from public s3 bucket
    tmp_file = aws.s3_download_file(source=f'resources/{filename}', destination=out_file)
    if tmp_file is not None:
        md5_sum = hashfile.md5(tmp_file)

    # if that fails try to download from flir server
    else:
        try:
            url = f'https://flir.netx.net/file/asset/{asset}/original/attachment'
            tmp_file, md5_sum = http_download_file(url, **options)
        except OSError as e:
            raise Exception(f'`{filename}` could not be downloaded - manual intervention is necessary') from e

    # finally
    os.rename(tmp_file, out_file)
    if md5_sum != target_md5:
        raise Exception(f'`{filename}` does not match the expected MD5 - manual intervention is necessary')
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
    file_winsdk = _download_from_alyx_or_flir(SPINNAKER_ASSET, SPINNAKER_FILENAME, SPINNAKER_MD5)
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
        file_zip = _download_from_alyx_or_flir(PYSPIN_ASSET, PYSPIN_FILENAME, PYSPIN_MD5)
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
        with open(HARDWARE_SETTINGS_YAML) as fp:
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
            with open(RIG_SETTINGS_YAML) as fp:
                rig_settings = yaml.safe_load(fp)
        else:
            rig_settings = {}
        path_map = {'iblrig_local_data_path': 'DATA_FOLDER_PATH', 'iblrig_remote_data_path': 'REMOTE_DATA_FOLDER_PATH'}
        for new_key, old_key in path_map.items():
            rig_settings[new_key] = old_settings[old_key].rstrip('\\')
            if rig_settings[new_key].endswith(r'\Subjects'):
                rig_settings[new_key] = rig_settings[new_key][: -len(r'\Subjects')]
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
    parser.add_argument('--subject_name', help='name of subject (optional if service-uri provided)', type=str)
    parser.add_argument(
        '--profile', default='default', help='camera configuration name, found in "device_cameras" map of hardware_settings.yaml'
    )
    parser.add_argument(
        '--service-uri',
        required=False,
        nargs='?',
        default=False,
        type=str,
        help='the service URI to listen to messages on. pass ":<port>" to specify port only.',
    )
    parser.add_argument('--debug', action='store_true', help='enable debugging mode')
    args = parser.parse_args()

    if args.subject_name is None and args.service_uri is False:
        parser.error('--subject-name is mandatory if --service-uri has not been provided.')

    setup_logger(name='iblrig', level='DEBUG' if args.debug else 'INFO')
    service_uri = args.service_uri
    # Technically `prepare_video_service` should behave the same as `prepare_video_session` if the service_uri arg is
    # False but until fully tested, let's call the old function
    if service_uri is False:
        # TODO Use CameraSession object and remove prepare_video_session and prepare_video_service
        prepare_video_session(args.subject_name, args.profile, debug=args.debug)
    else:
        log_level = 'DEBUG' if args.debug else 'INFO'
        session = CameraSessionNetworked(subject=args.subject_name, config_name=args.profile, log_level=log_level)
        asyncio.run(session.run(service_uri))


def validate_video_cmd():
    parser = argparse.ArgumentParser(prog='validate_video', description='Validate video session.')
    parser.add_argument('video_path', help='Path to the video file', type=str)
    parser.add_argument(
        'configuration', help='name of the configuration (default: default)', nargs='?', default='default', type=str
    )
    parser.add_argument('camera_name', help='name of the camera (default: left)', nargs='?', default='left', type=str)
    args = parser.parse_args()

    hwsettings: HardwareSettings = load_pydantic_yaml(HardwareSettings)
    file_path = Path(args.video_path)
    configuration = hwsettings.device_cameras.get(args.configuration, None)
    camera = configuration.get(args.camera_name, None) if configuration is not None else None

    if not file_path.exists():
        print(f'File not found: {file_path}')
    elif not file_path.is_file() or file_path.suffix != '.avi':
        print(f'Not a video file: {file_path}')
    elif configuration is None:
        print(f'No such configuration: {configuration}')
    elif configuration is None:
        print(f'No such camera: {camera}')
    else:
        validate_video(video_path=file_path, config=camera)


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
    ref = ConversionMixin.path2ref(video_path, as_dict=False)
    log.info('Checking %s camera for session %s', label_from_path(video_path), ref)
    if not video_path.exists():
        log.critical('Raw video file does not exist: %s', video_path)
        return False
    elif video_path.stat().st_size == 0:
        log.critical('Raw video file empty: %s', video_path)
        return False
    try:
        meta = get_video_meta(video_path)
        duration = meta.duration.total_seconds()
        ok = meta.length > 0 and duration > 0.0
        log.log(20 if meta.length > 0 else 40, 'N frames = %i', meta.length)
        log.log(20 if duration > 0 else 40, 'Duration = %.2f', duration)
        if config.HEIGHT and meta.height != config.HEIGHT:
            ok = False
            log.warning('Frame height = %i; expected %i', config.HEIGHT, meta.height)
        if config.WIDTH and meta.width != config.WIDTH:
            log.warning('Frame width = %i; expected %i', config.WIDTH, meta.width)
            ok = False
        if config.FPS and meta.fps != config.FPS:
            log.warning('Frame rate = %i; expected %i', config.FPS, meta.fps)
            ok = False
    except AssertionError:
        log.critical('Failed to open video file: %s', video_path)
        return False

    # Check frame data
    count, gpio = load_embedded_frame_data(video_path.parents[1], label_from_path(video_path))
    dropped = count[-1] - (meta.length - 1)
    if dropped != 0:  # Log ERROR if > .1% frames dropped, otherwise log WARN
        pct_dropped = dropped / (count[-1] + 1) * 100
        level = 30 if pct_dropped < 0.1 else 40
        log.log(level, 'Missed frames (%.2f%%) - frame data N = %i; video file N = %i', pct_dropped, count[-1] + 1, meta.length)
        ok = False
    if len(count) != meta.length:
        log.critical('Frame count / video frame mismatch - frame counts = %i; video frames = %i', len(count), meta.length)
        ok = False
    if config.SYNC_LABEL:
        min_events = 10  # The minimum expected number of GPIO events
        if all(ch is None for ch in gpio):
            log.error('No GPIO events detected.')
            ok = False
        else:
            for i, ch in enumerate(gpio):
                if ch:
                    log.log(30 if len(ch['indices']) < min_events else 20, '%i event(s) on GPIO #%i', len(ch['indices']), i + 1)
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
            value_error.add_note(str(HARDWARE_SETTINGS_YAML))  # py 3.11
        raise value_error from ex
    except KeyError as ex:
        raise ValueError(f'Config "{config_name}" not in "device_cameras" hardware settings.') from ex
    workflows = config.pop('BONSAI_WORKFLOW')
    cameras = [k for k in config if k != 'BONSAI_WORKFLOW']
    params = {f'{k.capitalize()}CameraIndex': config[k].INDEX for k in cameras}
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


async def prepare_video_service(config_name: str, debug: bool = False, service_uri=None, subject_name=None):
    """
    Setup and record video.

    Parameters
    ----------
    config_name : str
        Camera configuration name, found in "device_cameras" map of hardware_settings.yaml.
    debug : bool
        Bonsai debug mode and verbose logging.
    service_uri : str
        The service URI.
    """
    assert HAS_SPINNAKER
    assert HAS_PYSPIN

    com, _ = await get_server_communicator(service_uri, 'cameras')

    if not (com or subject_name):
        raise ValueError('Please provide a subject name or service_uri.')

    # Initialize a session for paths and settings
    session = EmptySession(subject=subject_name or '', interactive=False)

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
    params = {f'{k.capitalize()}CameraIndex': config[k].INDEX for k in cameras}

    # align cameras
    if workflows.setup:
        video_pyspin.enable_camera_trigger(enable=False)
        call_bonsai(workflows.setup, params, debug=debug)

    # Wait for initialization
    if com:
        # TODO Add exp info callback for main sync determination
        data, addr = await com.on_event(net.base.ExpMessage.EXPINIT)
        exp_ref = (data or {}).get('exp_ref')
        assert exp_ref, 'No experiment reference found'
        if isinstance(exp_ref, str):
            exp_ref = ConversionMixin.ref2dict(exp_ref)
        assert not subject_name or (subject_name == exp_ref['subject'])
        session_path = session.paths.LOCAL_SUBJECT_FOLDER.joinpath(
            exp_ref['subject'], str(exp_ref['date']), f'{exp_ref["sequence"]:03}'
        )
    else:
        session_path = session.paths.SESSION_FOLDER

    raw_data_folder = session_path.joinpath('raw_video_data')
    raw_data_folder.mkdir(parents=True, exist_ok=True)

    # initialize video
    filenamevideo = '_iblrig_{}Camera.raw.avi'
    filenameframedata = '_iblrig_{}Camera.frameData.bin'
    for k in map(str.capitalize, cameras):
        params[f'FileName{k}'] = str(raw_data_folder / filenamevideo.format(k.lower()))
        params[f'FileName{k}Data'] = str(raw_data_folder / filenameframedata.format(k.lower()))
    video_pyspin.enable_camera_trigger(enable=True)
    bonsai_process = call_bonsai(workflows.recording, params, wait=False, debug=debug)

    copier = VideoCopier(session_path=session_path, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
    description = copier.config2stub(config, raw_data_folder.name)
    if com:
        await com.init({'experiment_description': description}, addr=addr)
        log.info('initialized.')
        # Wait for task to begin
        data, addr = await com.on_event(net.base.ExpMessage.EXPSTART)
    else:
        input('PRESS ENTER TO START CAMERAS')

    # Save the stub files locally and in the remote repo for future copy script to use
    copier.initialize_experiment(acquisition_description=copier.config2stub(config, raw_data_folder.name))

    video_pyspin.enable_camera_trigger(enable=False)
    if com:
        await com.start(ConversionMixin.dict2ref(exp_ref), addr=addr)  # Let behaviour PC know acquisition has started
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
    com.close()


class CameraSession(EmptySession):
    def __init__(self, subject=None, config_name='default', **kwargs):
        """

        Parameters
        ----------
        subject : str, optional
            The subject name.
        config_name : str='default'
            The name of the camera configuration key in the hardware settings to use.

        Attributes
        ----------
        status : str
            This status will be returned when messages received during the main loop and determines response to
            remote events.
        communicator : iblutil.io.net.app.EchoProtocol
            A Communicator object that can be used to communicate with the behaviour rig.
        """
        self._status = None
        self.copier = None  # The VideoSession copier; created by _init_paths
        if kwargs.get('append'):
            raise NotImplementedError
        super().__init__(subject=subject or '', **kwargs)
        self.experiment_description = None
        self.bonsai_process = None
        try:
            self.config = self.hardware_settings.device_cameras[config_name]
        except AttributeError as ex:
            if hasattr(value_error := ValueError('"No camera config in hardware_settings.yaml file."'), 'add_note'):
                value_error.add_note(str(HARDWARE_SETTINGS_YAML))  # py 3.11
            raise value_error from ex
        except KeyError as ex:
            raise ValueError(f'Config "{config_name}" not in "device_cameras" hardware settings.') from ex

    def _init_paths(self, exp_ref: dict = None, **_):
        if not exp_ref:
            self.paths = super()._init_paths(False)  # not sure why super class doesn't do the assignment...
            for key in ('VISUAL_STIM_FOLDER', 'TASK_COLLECTION', 'DATA_FILE_PATH'):
                del self.paths[key]
        else:
            self.paths['SESSION_FOLDER'] = self.paths['LOCAL_SUBJECT_FOLDER'].joinpath(
                exp_ref['subject'], str(exp_ref['date']), f'{exp_ref["sequence"]:03}'
            )
            # Update session info
            self.session_info['SESSION_NUMBER'] = int(exp_ref['sequence'])
            self.session_info['SUBJECT_NAME'] = exp_ref['subject']
        self.paths['SESSION_RAW_DATA_FOLDER'] = self.paths['SESSION_FOLDER'].joinpath('raw_video_data')
        self.copier = VideoCopier(
            session_path=self.paths['SESSION_FOLDER'], remote_subjects_folder=self.paths['REMOTE_SUBJECT_FOLDER']
        )
        return self.paths

    @property
    def status(self):
        return self._status

    @property
    def one(self):
        """Return ONE instance.

        Unlike super class getter, this method will always instantiate ONE, allowing subclasses to update with an Alyx
        token from a remotely connected rig.  This instance is used for formatting the experiment reference string.

        Returns
        -------
        one.api.One
            An instance of ONE.
        """
        if super().one is None:
            self._one = OneAlyx(silent=True, mode='local')
        return self._one

    def _setup_loggers(self, level='INFO', **_):
        self.logger = setup_logger(name='iblrig', level=level)

    @property
    def cameras(self):
        return [k for k in self.config or [] if k != 'BONSAI_WORKFLOW']

    def _get_bonsai_params(self):
        raw_data_folder = self.paths['SESSION_RAW_DATA_FOLDER']
        filenamevideo = '_iblrig_{}Camera.raw.avi'
        filenameframedata = '_iblrig_{}Camera.frameData.bin'
        cameras = self.cameras
        params = {f'{k.capitalize()}CameraIndex': self.config[k].INDEX for k in cameras}
        for k in map(str.capitalize, self.cameras):
            params[f'FileName{k}'] = str(raw_data_folder / filenamevideo.format(k.lower()))
            params[f'FileName{k}Data'] = str(raw_data_folder / filenameframedata.format(k.lower()))
        return params

    def run_setup_workflow(self):
        workflows = self.config.get('BONSAI_WORKFLOW')
        # align cameras
        if workflows.setup:
            video_pyspin.enable_camera_trigger(enable=False)
            params = {k: v for k, v in self._get_bonsai_params().items() if k.endswith('CameraIndex')}
            call_bonsai(workflows.setup, params, debug=self.logger.level == 10, wait=True)

    def initialize_recording(self):
        workflows = self.config.get('BONSAI_WORKFLOW')
        video_pyspin.enable_camera_trigger(enable=True)
        params = self._get_bonsai_params()
        self.bonsai_process = call_bonsai(workflows.recording, params, wait=False, debug=self.logger.level == 10)
        self.experiment_description = self.copier.config2stub(self.config, self.paths['SESSION_RAW_DATA_FOLDER'].name)
        self._status = net.base.ExpStatus.INITIALIZED

    def start_recording(self):
        # Save the stub files locally and in the remote repo for future copy script to use
        assert self.status is net.base.ExpStatus.INITIALIZED
        self.paths['SESSION_RAW_DATA_FOLDER'].mkdir(parents=True, exist_ok=True)
        self.copier.initialize_experiment(acquisition_description=self.experiment_description)
        video_pyspin.enable_camera_trigger(enable=False)
        self._status = net.base.ExpStatus.RUNNING
        self.logger.info('To terminate video acquisition, please stop and close Bonsai workflow.')

    def finalize_recording(self):
        process_finished = self.bonsai_process and self.bonsai_process.returncode is not None
        assert self.status is net.base.ExpStatus.STOPPED and process_finished
        # Check video files were saved and configured correctly
        video_files = (Path(v) for v in self._get_bonsai_params().values() if isinstance(v, str) and v.endswith('.avi'))
        for video_file in video_files:
            validate_video(video_file, self.config[label_from_path(video_file)])

        self.paths['SESSION_FOLDER'].joinpath('transfer_me.flag').touch()
        # remove empty-folders and parent-folders
        if not any(self.paths['SESSION_RAW_DATA_FOLDER'].iterdir()):
            os.removedirs(self.paths['SESSION_RAW_DATA_FOLDER'])

    def stop_recording(self):
        if self.bonsai_process and self.bonsai_process.poll() is None:
            self.bonsai_process.terminate()
            self._status = net.base.ExpStatus.STOPPED
        self.logger.info('Video acquisition session finished.')
        self.finalize_recording()

    def run(self):
        assert self.session_info['SUBJECT_NAME']
        self.run_setup_workflow()
        self._status = net.base.ExpStatus.CONNECTED
        self.initialize_recording()
        input('PRESS ENTER TO START CAMERAS')
        self.start_recording()
        self._status = net.base.ExpStatus.RUNNING
        self.bonsai_process.wait()
        self._status = net.base.ExpStatus.STOPPED
        self.stop_recording()


class CameraSessionNetworked(CameraSession):
    def __init__(self, subject=None, config_name='default', **kwargs):
        """
        A camera session that listens for run commands from a remote computer.

        Parameters
        ----------
        subject : str, optional
            The subject name.
        config_name : str='default'
            The name of the camera configuration key in the hardware settings to use.

        Attributes
        ----------
        status : str
            This status will be returned when messages received during the main loop and determines response to
            remote events.
        communicator : iblutil.io.net.app.EchoProtocol
            A Communicator object that can be used to communicate with the behaviour rig.
        """
        self.communicator = None
        self._async_tasks = set()  # set of async tasks to await, namely the Bonsai process and remote com
        super().__init__(subject=subject, config_name=config_name, **kwargs)

    async def listen(self, service_uri=None):
        """
        Listen for remote rig.

        Parameters
        ----------
        service_uri : str
            The service URI.
        """
        if self.communicator and self.communicator.is_connected:
            self.logger.warning('Already listening on %s. Please call `close` method first.', self.communicator.service_uri)
            return
        self.communicator, _ = await get_server_communicator(service_uri, 'cameras')
        self._status = net.base.ExpStatus.CONNECTED

    async def initialize_recording(self):
        workflows = self.config.get('BONSAI_WORKFLOW')
        video_pyspin.enable_camera_trigger(enable=True)
        debug = self.logger.level == 10
        self.bonsai_process = await call_bonsai_async(workflows.recording, self._get_bonsai_params(), debug=debug)
        self._async_tasks.add(asyncio.create_task(self.bonsai_process.wait(), name='bonsai'))
        self.experiment_description = self.copier.config2stub(self.config, self.paths['SESSION_RAW_DATA_FOLDER'].name)
        self._status = net.base.ExpStatus.INITIALIZED

    def start_recording(self):
        """Start cameras (i.e. spawn Bonsai process)."""
        task = next((t for t in self._async_tasks if t.get_name() == 'bonsai'), None)
        assert task and not task.done(), 'No Bonsai process found!'
        return super().start_recording()

    @property
    def is_connected(self) -> bool:
        """bool: True if communicator is connected."""
        return self.communicator and self.communicator.is_connected

    async def run(self, service_uri=None):
        """Main loop networked with behaviour rig."""
        if not self.is_connected:
            # raise RuntimeError('Not connected. Please run `listen` first.')
            await self.listen(service_uri)
        self.run_setup_workflow()
        while self.is_connected:
            # FIXME Run this as worker for asynchronicity
            # Ensure we are awaiting a message from the remote rig.
            # This task must be re-added each time a message is received.
            if not any(t.get_name() == 'remote' for t in self._async_tasks):
                task = asyncio.create_task(self.communicator.on_event(net.base.ExpMessage.any()), name='remote')
                self._async_tasks.add(task)
            if not any(t.get_name() == 'keyboard' for t in self._async_tasks):
                self._async_tasks.add(asyncio.create_task(anext(read_stdin()), name='keyboard'))
            # Await the next task outcome
            done, _ = await asyncio.wait(self._async_tasks, timeout=None, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                match task.get_name():
                    case 'keyboard':
                        if net.base.is_success(task):
                            await self._process_keyboard_input(task.result())
                    case 'remote':
                        if task.cancelled():
                            self.logger.debug('Remote com await cancelled')
                            self.logger.error('Remote communicator closed')
                            break  # TODO cleanup and interact with com closed callbacks
                        else:
                            await self._process_message(*task.result())
                    case 'bonsai':
                        # Bonsai process was ended, most likely it was closed
                        status = task.result()
                        if status != 0:  # TODO This can be added as done callback instead
                            self.logger.error('Bonsai error: %s', await self.bonsai_process.stderr.readline())
                        else:
                            self.logger.info('Bonsai camera acquisition stopped')
                        self._status = net.base.ExpStatus.STOPPED
                        # TODO We could send a message to remote here
                    case _:
                        raise NotImplementedError(f'Unexpected task "{task.get_name()}"')
                self._async_tasks.remove(task)
        self.close()

    def close(self):
        """End experiment and cleanup object.

        This should be called before destroying the session object.
        """
        for task in self._async_tasks:
            self.logger.info('Cancelling %s', task)
            task.cancel()
        self._async_tasks.clear()
        if self.communicator:
            self.communicator.close()

    def reset(self):
        """Reset object for next session."""
        self.close()
        assert self.communicator
        if not self.is_connected:
            self.listen(service_uri=self.communicator.service_uri)
        else:
            self._status = net.base.ExpStatus.CONNECTED
        self.session_info['SESSION_NUMBER'] = 0  # Ensure previous exp ref invalid
        assert self.exp_ref is None
        if self.bonsai_process and self.bonsai_process.returncode is None:
            self.bonsai_process.terminate()
        self.bonsai_process = None

    async def _process_message(self, data, addr, event):
        """Callback for all messages received during the main loop."""
        name = event.name.lower()
        if name.startswith('exp'):
            name = name[3:]
        fcn = getattr(self, 'on_' + name, None)
        assert callable(fcn)
        await fcn(data, addr)

    async def _process_keyboard_input(self, line):
        """Process user input from stdin."""
        if not (line := (line or '').strip().upper()):
            return
        self.logger.info('Received keyboard event: %s', line)
        match line:
            case 'QUIT':
                self.communicator.close()
            case line if line.startswith('QUIT!'):
                self.close()
            case 'START':
                if not self.exp_ref:
                    self.logger.error(
                        'No subject name provided. '
                        'Please re-instantiate with subject param or await INIT message from remote rig.'
                    )
                    return
                else:
                    await self.on_start([self.exp_ref, {}], None)
            case _:
                self.logger.error('Command "%s" not recognized. Options: "START", "QUIT" or "QUIT!"', line)

    async def on_init(self, data, addr):
        """Process init command from remote rig."""
        self.logger.info('INIT message received')
        assert (exp_ref := (data or {}).get('exp_ref')), 'No experiment reference found'
        if isinstance(exp_ref, str):
            exp_ref = self.one.ref2dict(exp_ref)
        # NB: Only the first match case for which predicate is true will be run so we can update the status dynamically
        match self.status:
            case net.base.ExpStatus.CONNECTED:
                subject_name = self.session_info['SUBJECT_NAME']
                assert not subject_name or (subject_name == exp_ref['subject'])
                self._init_paths(exp_ref)
                await self.initialize_recording()
                assert self.session_info['SUBJECT_NAME'] == exp_ref['subject']
                self.logger.info('initialized.')
            case net.base.ExpStatus.RUNNING:
                # Already running - this is fine so long as the exp refs match
                assert self.exp_ref == self.one.dict2ref(exp_ref)
                self.logger.warning('received init message while already running.')
            case net.base.ExpStatus.INITIALIZED:
                # Already initialized - this is fine so long as the exp refs match
                assert self.exp_ref == self.one.dict2ref(exp_ref)
                self.logger.warning('received init message while already initialized.')
            case net.base.ExpStatus.STOPPED:
                """
                Currently experiments aren't stopped remotely; therefore the user should
                use a new instantiation per experiment.

                If we implement a way to end all on the behaviour rig, this could simply
                re-initialize with the new exp ref.
                """
                self.logger.error('received init message after experiment ended. Please restart.')
            case _:
                raise NotImplementedError(f'Unexpected status "{self.status}"')
        data = ExpInfo(self.exp_ref, False, self.experiment_description)
        await self.communicator.init(self.status, data.to_dict(), addr=addr)

    async def on_start(self, data, addr):
        """Process init command from remote rig."""
        exp_ref, data = data
        S = net.base.ExpStatus  # noqa - shorten for readability in match-case
        if isinstance(exp_ref, str):
            exp_ref = self.one.ref2dict(exp_ref)
        match self.status:
            case S.CONNECTED:
                self.logger.error('Received EXPSTART before EXPINIT')
                subject_name = self.session_info['SUBJECT_NAME']
                assert not subject_name or (subject_name == exp_ref['subject'])
                self._init_paths(exp_ref)
                await self.initialize_recording()
                assert self.session_info['SUBJECT_NAME'] == exp_ref['subject']
                self.start_recording()
            case S.INITIALIZED:
                self.logger.info('START message received')
                self.start_recording()
            case S.RUNNING:
                remote_ref = self.one.dict2ref(exp_ref)
                if self.exp_ref == remote_ref:
                    self.logger.info('START message received; already running')
                else:
                    self.logger.error('START message for %s received; already running %s', remote_ref, self.exp_ref)
            case S.STOPPED:
                self.logger.error('received start message after experiment ended. Please restart.')
            case _:
                raise NotImplementedError
        data = ExpInfo(self.exp_ref, False, self.experiment_description).to_dict() | {'status': self.status}
        if addr:
            await self.communicator.start(self.exp_ref, data, addr=addr)  # Let behaviour PC know acquisition has started

    async def on_end(self, data, addr):
        self.logger.info('STOP message received')
        data = ExpInfo(self.exp_ref, False, self.experiment_description).to_dict() | {'status': self.status}
        await self.communicator.stop(data, addr=addr, immediately=False)

    async def on_interrupt(self, data, addr):
        self.logger.info('STOP message received')
        data = ExpInfo(self.exp_ref, False, self.experiment_description).to_dict() | {'status': self.status}
        await self.communicator.stop(data, addr=addr, immediately=True)

    async def on_cleanup(self, data, addr):
        self.logger.info('CLEANUP message received')
        data = ExpInfo(self.exp_ref, False, self.experiment_description).to_dict() | {'status': self.status}
        await self.communicator.stop(data, addr=addr, immediately=True)

    async def on_status(self, _, addr):
        self.logger.info('STATUS message received')
        await self.communicator.status(self.status, addr=addr)

    async def on_info(self, _, addr):
        self.logger.info('INFO message received')
        data = ExpInfo(self.exp_ref, False, self.experiment_description)
        await self.communicator.info(self.status, data.to_dict(), addr=addr)

    async def on_alyx(self, data, addr):
        base_url, token = data
        if token:
            self.logger.info('ALYX token received')
            update_alyx_token((base_url, token), addr, one=self.one)
        elif not self.one.offline and self.one.alyx.is_logged_in and self.one.alyx.base_url == base_url:
            # Send our token
            await self.communicator.alyx(self.one.alyx, addr=addr)
            self.logger.info('ALYX token sent')


if __name__ == '__main__':
    prepare_video_session_cmd()
