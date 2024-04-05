import datetime
import json
import logging
import os
import shutil
import socket
import traceback
import uuid
from os.path import samestat
from pathlib import Path

import ibllib.pipes.misc
import iblrig
import one.alf.files as alfiles
from ibllib.io import raw_data_loaders, session_params
from ibllib.pipes.misc import sleepless
from iblrig.raw_data_loaders import load_task_jsonable
from iblutil.io import hashfile
from one.util import ensure_list

log = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


@sleepless
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


class SessionCopier:
    """Initialize and copy session data to a remote server."""

    assert_connect_on_init = True
    """bool: Raise error if unable to write stub file to remote server."""

    _experiment_description = None
    """dict: The experiment description file used for the copy."""

    tag = f'{socket.gethostname()}_{uuid.getnode()}'
    """str: The device name (adds this to the experiment description stub file on the remote server)."""

    def __init__(self, session_path, remote_subjects_folder=None, tag=None):
        """
        Initialize and copy session data to a remote server.

        Parameters
        ----------
        session_path : str, pathlib.Path
            The partial or session path to copy.
        remote_subjects_folder : str, pathlib.Path
            The remote server path to which to copy the session data.
        tag : str
            The device name (adds this to the experiment description stub file on the remote server).
        """
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
        if self.state == 0:  # the session hasn't even been initialized: copy the stub to the remote
            log.info(f'{self.state}, {self.session_path}')
            self.initialize_experiment()
        if self.state == 1:  # the session is ready for copy
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
        State 3: the whole experiment is finalized and all data is on the server
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
            # padded_sequence ensures session path has zero padded number folder, e.g. 1 -> 001
            session_parts = alfiles.padded_sequence(self.session_path).parts[-3:]
            return self.remote_subjects_folder.joinpath(*session_parts)

    @property
    def file_experiment_description(self):
        """Returns the local experiment description file, if none found, returns one with the tag."""
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
        """Return the remote path to the remote stub file."""
        if self.remote_subjects_folder:
            return session_params.get_remote_stub_name(self.remote_session_path, device_id=self.tag)

    @property
    def remote_experiment_description_stub(self):
        return session_params.read_params(self.file_remote_experiment_description)

    def _copy_collections(self):
        """
        Copy collections defined in experiment description file.

        This is the method to subclass for pre- and post- copy routines.

        Returns
        -------
        bool
            True if transfer successfully completed.
        """
        status = True
        exp_pars = session_params.read_params(self.session_path)
        collections = set()
        # First glob on each collection pattern to find all folders to transfer
        for collection in session_params.get_collections(exp_pars, flat=True):
            folders = filter(Path.is_dir, self.session_path.glob(collection))
            _collections = list(map(lambda x: x.relative_to(self.session_path).as_posix(), folders))
            if not _collections:
                log.error(f'No collection(s) matching "{collection}" found')
                status = False
                continue
            collections.update(_collections)

        # Attempt to copy each folder
        for collection in collections:
            local_collection = self.session_path.joinpath(collection)
            assert local_collection.exists(), f'local collection "{collection}" no longer exists'
            log.info(f'transferring {self.session_path} - {collection}')
            remote_collection = self.remote_session_path.joinpath(collection)
            if remote_collection.exists():
                # this is far from ideal: we currently recopy all files even if some already copied
                log.warning(f'Collection {remote_collection} already exists, removing')
                shutil.rmtree(remote_collection)
            status &= copy_folders(local_collection, remote_collection)
        return status

    def copy_collections(self):
        """
        Recursively copies the collection folders into the remote session path.

        Do not overload, overload _copy_collections instead.
        """
        if self.glob_file_remote_copy_status('complete'):
            log.warning(
                f'Copy already complete for {self.session_path},'
                f' remove {self.glob_file_remote_copy_status("complete")} to force'
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
                    raise RuntimeError(f'Failed to write data to remote device at: {remote_stub_file}. \n {e}') from e
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
        """At the end of the copy, check if all the files are there and if so, aggregate the device files."""
        ready_to_finalize = 0
        # List the stub files in _devices folder
        files_stub = list(self.file_remote_experiment_description.parent.glob('*.yaml'))
        if number_of_expected_devices is None:
            number_of_expected_devices = len(files_stub)
        log.debug(f'Number of expected devices is {number_of_expected_devices}')

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

        if ready_to_finalize > number_of_expected_devices:
            log.error('More stub files (%i) than expected devices (%i)', ready_to_finalize, number_of_expected_devices)
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

    def create_video_stub(self, config, collection='raw_video_data'):
        acquisition_description = self.config2stub(config, collection)
        session_params.write_params(self.session_path, acquisition_description)

    @staticmethod
    def config2stub(config: dict, collection: str = 'raw_video_data') -> dict:
        """
        Generate acquisition description stub from a camera config dict.

        Parameters
        ----------
        config : dict
            A cameras configuration dictionary, found in `device_cameras` of hardware_settings.yaml.
        collection : str
            The video output collection.

        Returns
        -------
        dict
            An acquisition description file stub.
        """
        cameras = {}
        for label, settings in filter(lambda itms: itms[0] != 'BONSAI_WORKFLOW', config.items()):
            settings_mod = {k.lower(): v for k, v in settings.items() if v is not None and k != 'INDEX'}
            cameras[label] = dict(collection=collection, **settings_mod)
        acq_desc = {'devices': {'cameras': cameras}, 'version': '1.0.0'}
        return acq_desc

    def initialize_experiment(self, acquisition_description=None, **kwargs):
        if not acquisition_description:
            # creates the acquisition description stub if not found, and then read it
            if not self.file_experiment_description.exists():
                raise FileNotFoundError(self.file_experiment_description)
            acquisition_description = session_params.read_params(self.file_experiment_description)
        self._experiment_description = acquisition_description
        super().initialize_experiment(acquisition_description=acquisition_description, **kwargs)


class BehaviorCopier(SessionCopier):
    tag = 'behavior'
    assert_connect_on_init = False

    @property
    def experiment_description(self):
        return session_params.read_params(self.session_path)

    def _copy_collections(self):
        """Patch settings files before copy.

        Before copying the collections, this method checks that the behaviour data are valid. The
        following checks are made:

        #. Check at least 1 task collection in experiment description. If not, return.
        #. For each collection, check for task settings. If any are missing, return.
        #. If SESSION_END_TIME is missing, assumes task crashed. If so and task data missing and
           not a chained protocol (i.e. it is the only task collection), assume a dud and remove
           the remote stub file.  Otherwise, patch settings with total trials, end time, etc.

        Returns
        -------
        bool
            True if transfer successfully completed.

        """
        collections = session_params.get_task_collection(self.experiment_description)
        if not collections:
            log.error(f'Skipping: no task collections defined for {self.session_path}')
            return False
        for collection in (collections := ensure_list(collections)):
            task_settings = raw_data_loaders.load_settings(self.session_path, task_collection=collection)
            if task_settings is None:
                log.info(f'Skipping: no task settings found for {self.session_path}')
                return False  # may also want to remove session here if empty
            # here if the session end time has not been labeled we assume that the session crashed, and patch the settings
            if task_settings['SESSION_END_TIME'] is None:
                jsonable = self.session_path.joinpath(collection, '_iblrig_taskData.raw.jsonable')
                if not jsonable.exists():
                    log.info(f'Skipping: no task data found for {self.session_path}')
                    # No local data and only behaviour stub in remote; assume dud and remove entire session
                    if (
                        self.remote_session_path.exists()
                        and len(collections) == 1
                        and len(list(self.file_remote_experiment_description.parent.glob('*.yaml'))) <= 1
                    ):
                        shutil.rmtree(self.remote_session_path)  # remove likely dud
                    return False
                trials, bpod_data = load_task_jsonable(jsonable)
                ntrials = trials.shape[0]
                # We have the case where the session hard crashed.
                # Patch the settings file to wrap the session and continue the copying.
                log.warning(f'Recovering crashed session {self.session_path}')
                settings_file = self.session_path.joinpath(collection, '_iblrig_taskSettings.raw.json')
                with open(settings_file) as fid:
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
        log.critical(f'{self.state}, {self.session_path}')
        return super()._copy_collections()  # proceed with copy

    def finalize_copy(self, number_of_expected_devices=None):
        """If main sync is bpod, expect a single stub file."""
        if number_of_expected_devices is None and session_params.get_sync(self.remote_experiment_description_stub) == 'bpod':
            number_of_expected_devices = 1
        super().finalize_copy(number_of_expected_devices=number_of_expected_devices)


class EphysCopier(SessionCopier):
    tag = 'ephys'
    assert_connect_on_init = True

    def initialize_experiment(self, acquisition_description=None, nprobes=None, main_sync=True, **kwargs):
        if not acquisition_description:
            acquisition_description = {'devices': {'neuropixel': {}}}
            neuropixel = acquisition_description['devices']['neuropixel']
            if nprobes is None:
                nprobes = len(list(self.session_path.glob('**/*.ap.bin')))
            for n in range(nprobes):
                name = f'probe{n:02}'
                neuropixel[name] = {'collection': f'raw_ephys_data/{name}', 'sync_label': 'imec_sync'}
            sync_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'sync', 'nidq.yaml')
            acquisition_description = acquisition_description if neuropixel else {}
            if main_sync:
                acquisition_description.update(session_params.read_params(sync_file))

        self._experiment_description = acquisition_description
        super().initialize_experiment(acquisition_description=acquisition_description, **kwargs)
        # once the session folders have been initialized, create the probe folders
        for n in range(nprobes):
            self.session_path.joinpath('raw_ephys_data', f'probe{n:02}').mkdir(exist_ok=True, parents=True)

    def _copy_collections(self):
        """Here we overload the copy to be able to rename the probes properly and also create the insertions."""
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
        except Exception:
            log.error(traceback.print_exc())
            log.info('Probe creation failed, please create the probe insertions manually. Continuing transfer...')
        return copy_folders(
            local_folder=self.session_path.joinpath('raw_ephys_data'),
            remote_folder=self.remote_session_path.joinpath('raw_ephys_data'),
            overwrite=True,
        )
