import abc
import ctypes
import os
import shutil
import traceback
from collections.abc import Callable
from os.path import samestat
from pathlib import Path
from typing import Any

import ibllib.pipes.misc
import iblrig
from ibllib.io import session_params
from iblutil.io import hashfile
from iblutil.util import setup_logger

log = setup_logger('iblrig', level='INFO')

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _set_thread_execution(state: int) -> None:
    """
    Set the thread execution state to control system power management.

    This function sets the thread execution state to control system power
    management on Windows systems. It prevents the system from entering
    sleep or idle mode while a specific state is active.

    Parameters
    ----------
    state : int
        The desired thread execution state. Use ES_CONTINUOUS and ES_SYSTEM_REQUIRED
        constants to specify the state.

    Raises
    ------
    OSError
        If there is an issue setting the thread execution state.
    """
    if os.name == 'nt':
        result = ctypes.windll.kernel32.SetThreadExecutionState(state)
        if result == 0:
            raise OSError('Failed to set thread execution state.')


def long_running(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to ensure that the system doesn't enter sleep or idle mode during a long-running task.

    This decorator wraps a function and sets the thread execution state to prevent
    the system from entering sleep or idle mode while the decorated function is
    running.

    Parameters
    ----------
    func : callable
        The function to decorate.

    Returns
    -------
    callable
        The decorated function.
    """

    def inner(*args, **kwargs) -> Any:
        _set_thread_execution(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        result = func(*args, **kwargs)
        _set_thread_execution(ES_CONTINUOUS)
        return result

    return inner


@long_running
def _copy2_checksum(src: str, dst: str, *args, **kwargs) -> str:
    """
    Copy a file from source to destination with checksum verification.

    This function copies a file from the source path to the destination path
    while verifying the BLAKE2B hash of the source and destination files. If the
    BLAKE2B hashes do not match after copying, an OSError is raised.

    Parameters
    ----------
    src : str
        The path to the source file.
    dst : str
        The path to the destination file.
    *args, **kwargs
        Additional arguments and keyword arguments to pass to `shutil.copy2`.

    Returns
    -------
    str
        The path to the copied file.

    Raises
    ------
    OSError
        If the BLAKE2B hashes of the source and destination files do not match.
    """
    log.info(f'Processing `{src}`:')
    log.info('  - calculating hash of local file')
    src_md5 = hashfile.blake2b(src, False)
    if os.path.exists(dst) and samestat(os.stat(src), os.stat(dst)):
        log.info('  - file already exists at destination')
        log.info('  - calculating hash of remote file')
        if src_md5 == hashfile.blake2b(dst, False):
            log.info('  - local and remote BLAKE2B hashes match, skipping copy')
            return dst
        else:
            log.info('  - local and remote hashes DO NOT match')
    log.info(f'  - copying file to `{dst}`')
    return_val = shutil.copy2(src, dst, *args, **kwargs)
    log.info('  - calculating hash of remote file')
    if not src_md5 == hashfile.blake2b(dst, False):
        raise OSError(f'Error copying {src}: hash mismatch.')
    log.info('  - local and remote hashes match, copy successful')
    return return_val


def copy_folders(local_folder: Path, remote_folder: Path, overwrite: bool = False) -> bool:
    """
    Copy folders and files from a local location to a remote location.

    This function copies all folders and files from a local directory to a
    remote directory. It provides options to overwrite existing files in
    the remote directory and ignore specific file patterns.

    Parameters
    ----------
    local_folder : Path
        The path to the local folder to copy from.
    remote_folder : Path
        The path to the remote folder to copy to.
    overwrite : bool, optional
        If True, overwrite existing files in the remote folder. Default is False.

    Returns
    -------
    bool
        True if the copying is successful, False otherwise.
    """
    status = True
    try:
        remote_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            local_folder,
            remote_folder,
            dirs_exist_ok=overwrite,
            ignore=shutil.ignore_patterns('transfer_me.flag'),
            copy_function=_copy2_checksum,
        )
    except OSError:
        log.error(traceback.format_exc())
        log.info(f'Could not copy {local_folder} to {remote_folder}')
        status = False
    return status


class SessionCopier(abc.ABC):
    assert_connect_on_init = False
    _experiment_description = None

    def __init__(self, session_path, remote_subjects_folder=None, tag=None):
        self.tag = tag or self.tag
        self.session_path = Path(session_path)
        self.remote_subjects_folder = Path(remote_subjects_folder) if remote_subjects_folder else None

    def __repr__(self):
        return f'{super().__repr__()} \n local: {self.session_path} \n remote: {self.remote_session_path}'

    @property
    def state(self):
        return self.get_state()[0]

    def run(self, number_of_expected_devices=None):
        """
        Runs the copy of this device experiment. It will try to get as far as possible in the copy
        process (from states 0 init experiment to state 3 finalize experiment) if possible, and
        return earlier if the process can't be completed.
        :return:
        """
        if self.state == -1:  # this case is not implemented automatically and corresponds to a hard reset
            log.info(f'{self.state}, {self.session_path}')
            shutil.rmtree(self.remote_session_path)
            self.initialize_experiment()
        if self.state == 0:  # the session hasn't even been initialzed: copy the stub to the remote
            log.info(f'{self.state}, {self.session_path}')
            self.initialize_experiment()
        if self.state == 1:  # the session
            log.info(f'{self.state}, {self.session_path}')
            self.copy_collections()
        if self.state == 2:
            log.info(f'{self.state}, {self.session_path}')
            self.finalize_copy(number_of_expected_devices=number_of_expected_devices)
        if self.state == 3:
            log.info(f'{self.state}, {self.session_path}')

    def get_state(self):
        """
        Gets the current copier state.
        State 0: this device experiment has not been initialized for this device
        State 1: this device experiment is initialized (the experiment description stub is present on the remote)
        State 2: this device experiment is copied on the remote server, but other devices copies are still pending
        State 3: the whole experiment is finalized and all of the data is on the server
        :return:
        """
        if self.remote_subjects_folder is None or not self.remote_subjects_folder.exists():
            return None, f'Remote subjects folder {self.remote_subjects_folder} set to Null or unreachable'
        if not self.file_remote_experiment_description.exists():
            return 0, f'Copy object not registered on server: {self.file_remote_experiment_description} does not exist'
        status_file = self.glob_file_remote_copy_status()
        if status_file is None:
            status_file = self.file_remote_experiment_description.with_suffix('.status_pending')
            status_file.touch()
            log.warning(f'{status_file} not found and created')
        if status_file.name.endswith('pending'):
            return 1, f'Copy pending {self.file_remote_experiment_description}'
        elif status_file.name.endswith('complete'):
            return 2, f'Copy complete {self.file_remote_experiment_description}'
        elif status_file.name.endswith('final'):
            return 3, f'Copy finalized {self.file_remote_experiment_description}'

    @property
    def experiment_description(self):
        return self._experiment_description

    @property
    def remote_session_path(self):
        if self.remote_subjects_folder:
            session_parts = self.session_path.as_posix().split('/')[-3:]
            return self.remote_subjects_folder.joinpath(*session_parts)

    @property
    def file_experiment_description(self):
        """
        Returns the local experiment description file, if none found, returns one with the tag
        :return:
        """
        return next(
            self.session_path.glob('_ibl_experiment.description*'),
            self.session_path.joinpath(f'_ibl_experiment.description_{self.tag}.yaml'),
        )

    def glob_file_remote_copy_status(self, status='*'):
        """status: pending / complete"""
        fr = self.file_remote_experiment_description
        return next(fr.parent.glob(f'{fr.stem}.status_{status}'), None) if fr else None

    @property
    def file_remote_experiment_description(self):
        if self.remote_subjects_folder:
            return session_params.get_remote_stub_name(self.remote_session_path, device_id=self.tag)

    @property
    def remote_experiment_description_stub(self):
        return session_params.read_params(self.file_remote_experiment_description)

    def _copy_collections(self):
        """
        This is the method to subclass and implement
        :return:
        """
        status = True
        exp_pars = session_params.read_params(self.session_path)
        collections = set(session_params.get_collections(exp_pars).values())
        for collection in collections:
            local_collection = self.session_path.joinpath(collection)
            if not local_collection.exists():
                log.error(f"Collection {local_collection} doesn't exist")
                status = False
                continue
            log.info(f'transferring {self.session_path} - {collection}')
            remote_collection = self.remote_session_path.joinpath(collection)
            if remote_collection.exists():
                # this is far from ideal, but here rsync-diff backup is not the right tool for syncing
                # and will error out if the remote collection already exists
                log.warning(f'Collection {remote_collection} already exists, removing')
                shutil.rmtree(remote_collection)
            status &= copy_folders(local_collection, remote_collection)
        return status

    def copy_collections(self):
        """
        Recursively copies the collection folders into the remote session path
        Do not overload, overload _copy_collections instead
        :return:
        """
        if self.glob_file_remote_copy_status('complete'):
            log.warning(
                f"Copy already complete for {self.session_path},"
                f" remove {self.glob_file_remote_copy_status('complete')} to force"
            )
            return True
        status = self._copy_collections()
        # post copy stuff: rename the pending flag to complete
        if status:
            pending_file = self.glob_file_remote_copy_status('pending')
            pending_file.rename(pending_file.with_suffix('.status_complete'))
            if self.session_path.joinpath('transfer_me.flag').exists():
                self.session_path.joinpath('transfer_me.flag').unlink()
        return status

    def initialize_experiment(self, acquisition_description=None, overwrite=True):
        """
        Copy acquisition description yaml to the server and local transfers folder.

        Parameters
        ----------
        acquisition_description : dict
            The data to write to the experiment.description.yaml file.
        overwrite : bool
            If true, overwrite any existing file with the new one, otherwise, update the existing file.
        """
        if acquisition_description is None:
            acquisition_description = self.experiment_description

        assert acquisition_description

        # First attempt to add the remote description stub to the _device folder on the remote session
        if not self.remote_subjects_folder:
            log.info('The remote path is unspecified and remote experiment.description stub creation is omitted.')
        else:
            remote_stub_file = self.file_remote_experiment_description
            previous_description = (
                session_params.read_params(remote_stub_file) if remote_stub_file.exists() and not overwrite else {}
            )
            try:
                merged_description = session_params.merge_params(previous_description, acquisition_description)
                session_params.write_yaml(remote_stub_file, merged_description)
                for f in remote_stub_file.parent.glob(remote_stub_file.stem + '.status_*'):
                    f.unlink()
                remote_stub_file.with_suffix('.status_pending').touch()
                log.info(f'Written data to remote device at: {remote_stub_file}.')
            except Exception as e:
                if self.assert_connect_on_init:
                    raise Exception(f'Failed to write data to remote device at: {remote_stub_file}. \n {e}') from e
                log.warning(f'Failed to write data to remote device at: {remote_stub_file}. \n {e}')

        # then create on the local machine
        previous_description = (
            session_params.read_params(self.file_experiment_description)
            if self.file_experiment_description.exists() and not overwrite
            else {}
        )
        session_params.write_yaml(
            self.file_experiment_description, session_params.merge_params(previous_description, acquisition_description)
        )
        log.info(f'Written data to local session at : {self.file_experiment_description}.')

    def finalize_copy(self, number_of_expected_devices=None):
        """
        At the end of the copy, check if all the files are there and if so, aggregate the device files
        :return:
        """
        if number_of_expected_devices is None:
            log.warning(f'Number of expected devices is not specified, will not finalize this session {self.session_path}')
            return
        ready_to_finalize = 0
        files_stub = list(self.file_remote_experiment_description.parent.glob('*.yaml'))
        for file_stub in files_stub:
            ready_to_finalize += int(file_stub.with_suffix('.status_complete').exists())
            ad_stub = session_params.read_params(file_stub)
            # here we check the sync field of the device files
            if next(iter(ad_stub.get('sync', {})), None) != 'bpod' and number_of_expected_devices == 1:
                log.warning(
                    'Only bpod is supported for single device sessions, it seems you are '
                    'attempting to transfer a session with more than one device.'
                )
                return
        log.info(f'{ready_to_finalize}/{number_of_expected_devices} copy completion status')
        if ready_to_finalize == number_of_expected_devices:
            for file_stub in files_stub:
                session_params.aggregate_device(file_stub, self.remote_session_path.joinpath('_ibl_experiment.description.yaml'))
                file_stub.with_suffix('.status_complete').rename(file_stub.with_suffix('.status_final'))
            self.remote_session_path.joinpath('raw_session.flag').touch()


class VideoCopier(SessionCopier):
    tag = 'video'
    assert_connect_on_init = True

    def create_video_stub(self, nvideos=None):
        match len(list(self.session_path.joinpath('raw_video_data').glob('*.avi'))):
            case 3:
                stub_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'cameras', 'body_left_right.yaml')
            case 1:
                stub_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'cameras', 'left.yaml')
        acquisition_description = session_params.read_params(stub_file)
        session_params.write_params(self.session_path, acquisition_description)

    def initialize_experiment(self, acquisition_description=None, **kwargs):
        if not acquisition_description:
            # creates the acquisition description stub if not found, and then read it
            if not self.file_experiment_description.exists():
                self.create_video_stub()
            acquisition_description = session_params.read_params(self.file_experiment_description)
        self._experiment_description = acquisition_description
        super().initialize_experiment(acquisition_description=acquisition_description, **kwargs)


class BehaviorCopier(SessionCopier):
    tag = 'behavior'
    assert_connect_on_init = False

    @property
    def experiment_description(self):
        return session_params.read_params(self.session_path)


class EphysCopier(SessionCopier):
    tag = 'spikeglx'
    assert_connect_on_init = True

    def initialize_experiment(self, acquisition_description=None, nprobes=None, **kwargs):
        if not acquisition_description:
            nprobes = nprobes or len(list(self.session_path.joinpath('raw_ephys_data').rglob('*.ap.bin')))
            match nprobes:
                case 1:
                    stub_name = 'single_probe.yaml'
                case 2:
                    stub_name = 'dual_probe.yaml'
            stub_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'neuropixel', stub_name)
            sync_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'sync', 'nidq.yaml')
            acquisition_description = session_params.read_params(stub_file)
            acquisition_description.update(session_params.read_params(sync_file))
        self._experiment_description = acquisition_description
        super().initialize_experiment(acquisition_description=acquisition_description, **kwargs)

    def _copy_collections(self):
        """
        Here we overload the copy to be able to rename the probes properly and also create the insertions
        :return:
        """
        log.info(f'Transferring ephys session: {self.session_path} to {self.remote_session_path}')
        ibllib.pipes.misc.rename_ephys_files(self.session_path)
        ibllib.pipes.misc.move_ephys_files(self.session_path)
        # copy the wiring files from template
        path_wiring = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'neuropixel', 'wirings')
        probe_model = '3A'
        for file_nidq_bin in self.session_path.joinpath('raw_ephys_data').glob('*.nidq.bin'):
            probe_model = '3B'
            shutil.copy(path_wiring.joinpath('nidq.wiring.json'), file_nidq_bin.with_suffix('.wiring.json'))
        for file_ap_bin in self.session_path.joinpath('raw_ephys_data').rglob('*.ap.bin'):
            shutil.copy(path_wiring.joinpath(f'{probe_model}.wiring.json'), file_ap_bin.with_suffix('.wiring.json'))
        try:
            ibllib.pipes.misc.create_alyx_probe_insertions(self.session_path)
        except BaseException:
            log.error(traceback.print_exc())
            log.info('Probe creation failed, please create the probe insertions manually. Continuing transfer...')
        return copy_folders(
            local_folder=self.session_path.joinpath('raw_ephys_data'),
            remote_folder=self.remote_session_path.joinpath('raw_ephys_data'),
            overwrite=True,
        )
