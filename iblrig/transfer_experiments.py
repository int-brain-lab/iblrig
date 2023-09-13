from pathlib import Path
from abc import ABC
import shutil
import traceback

import iblrig
from iblutil.util import setup_logger
from ibllib.io import session_params
from ibllib.pipes.misc import rsync_paths

log = setup_logger('iblrig', level='INFO')


class SessionCopier(ABC):
    tag = 'behavior'
    assert_connect_on_init = False

    def __init__(self, session_path, remote_subjects_folder=None, tag=None):
        self.tag = tag or self.tag
        self.session_path = Path(session_path)
        self.remote_subjects_folder = Path(remote_subjects_folder) if remote_subjects_folder else None

    def __repr__(self):
        return f"{super(SessionCopier, self).__repr__()} \n local: {self.session_path} \n remote: {self.remote_session_path}"

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
            log.info(f"{self.state}, {self.session_path}")
            shutil.rmtree(self.remote_session_path)
            self.initialize_experiment()
        if self.state == 0:  # the session hasn't even been initialzed: copy the stub to the remote
            log.info(f"{self.state}, {self.session_path}")
            self.initialize_experiment()
        if self.state == 1:  # the session
            log.info(f"{self.state}, {self.session_path}")
            self.copy_collections()
        if self.state == 2:
            log.info(f"{self.state}, {self.session_path}")
            self.finalize_copy(number_of_expected_devices=number_of_expected_devices)
        if self.state == 3:
            log.info(f"{self.state}, {self.session_path}")

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
        return session_params.read_params(self.session_path)

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
        return next(self.session_path.glob('_ibl_experiment.description*'),
                    self.session_path.joinpath(f'_ibl_experiment.description_{self.tag}.yaml'))

    def glob_file_remote_copy_status(self, status='*'):
        """ status: pending / complete """
        fr = self.file_remote_experiment_description
        return next(fr.parent.glob(f"{fr.stem}.status_{status}"), None) if fr else None

    @property
    def file_remote_experiment_description(self):
        if self.remote_subjects_folder:
            return session_params.get_remote_stub_name(
                self.remote_session_path, device_id=self.tag)

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
                log.error(f'Collection {local_collection} doesn\'t exist')
                status = False
                continue
            log.info(f'transferring {self.session_path} - {collection}')
            remote_collection = self.remote_session_path.joinpath(collection)
            if remote_collection.exists():
                # this is far from ideal, but here rsync-diff backup is not the right tool for syncing
                # and will error out if the remote collection already exists
                log.warning(f'Collection {remote_collection} already exists, removing')
                shutil.rmtree(remote_collection)
            status &= rsync_paths(local_collection, remote_collection)
        return status

    def copy_collections(self):
        """
        Recursively copies the collection folders into the remote session path
        Do not overload, overload _copy_collections instead
        :return:
        """
        if self.glob_file_remote_copy_status('complete'):
            log.warning(f"Copy already complete for {self.session_path},"
                        f" remove {self.glob_file_remote_copy_status('complete')} to force")
            return True
        status = self._copy_collections()
        # post copy stuff: rename the pending flag to complete
        if status:
            pending_file = self.glob_file_remote_copy_status('pending')
            pending_file.rename(pending_file.with_suffix('.status_complete'))
            if self.session_path.joinpath('transfer_me.flag').exists():
                self.session_path.joinpath('transfer_me.flag').unlink()
        return status

    def initialize_experiment(self, acquisition_description=None, overwrite=False):
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
            previous_description = session_params.read_params(remote_stub_file)\
                if remote_stub_file.exists() and not overwrite else {}
            try:
                merged_description = session_params.merge_params(previous_description, acquisition_description)
                session_params.write_yaml(remote_stub_file, merged_description)
                for f in remote_stub_file.parent.glob(remote_stub_file.name + '.status_*'):
                    f.unlink()
                remote_stub_file.with_suffix('.status_pending').touch()
                log.info(f'Written data to remote device at: {remote_stub_file}.')
            except Exception as e:
                if self.assert_connect_on_init:
                    raise Exception(f'Failed to write data to remote device at: {remote_stub_file}. \n {e}') from e
                log.warning(f'Failed to write data to remote device at: {remote_stub_file}. \n {e}')

        # then create on the local machine
        previous_description = session_params.read_params(self.file_experiment_description)\
            if self.file_experiment_description.exists() and not overwrite else {}
        session_params.write_yaml(
            self.file_experiment_description, session_params.merge_params(previous_description, acquisition_description))
        log.info(f'Written data to local session at : {self.file_experiment_description}.')

    def finalize_copy(self, number_of_expected_devices=None):
        """
        At the end of the copy, check if all the files are there and if so, aggregate the device files
        :return:
        """
        assert number_of_expected_devices
        ready_to_finalize = 0
        files_stub = list(self.file_remote_experiment_description.parent.glob('*.yaml'))
        for file_stub in files_stub:
            ready_to_finalize += int(file_stub.with_suffix('.status_complete').exists())
            ad_stub = session_params.read_params(file_stub)
            # here we check the sync field of the device files
            if next(iter(ad_stub.get('sync', {})), None) != 'bpod' and number_of_expected_devices == 1:
                log.warning("Only bpod is supported for single device sessions, it seems you are "
                            "attempting to transfer a session with more than one device.")
                return
        log.info(f"{ready_to_finalize}/{number_of_expected_devices} copy completion status")
        if ready_to_finalize == number_of_expected_devices:
            for file_stub in files_stub:
                session_params.aggregate_device(
                    file_stub, self.remote_session_path.joinpath('_ibl_experiment.description.yaml'))
                file_stub.with_suffix('.status_complete').rename(file_stub.with_suffix('.status_final'))
            self.remote_session_path.joinpath('raw_session.flag').touch()


class VideoCopier(SessionCopier):
    tag = 'video'
    assert_connect_on_init = True

    def initialize_experiment(self, acquisition_description=None, **kwargs):
        if not acquisition_description:
            stub_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'cameras', 'body_left_right.yaml')
            acquisition_description = session_params.read_params(stub_file)
        super(VideoCopier, self).initialize_experiment(acquisition_description=acquisition_description, **kwargs)


class BehaviorCopier(SessionCopier):
    pass


class EphysCopier(SessionCopier):
    tag = 'spikeglx'
    assert_connect_on_init = True

    def initialize_experiment(self, acquisition_description=None, nprobes=None, **kwargs):
        if not acquisition_description:
            nprobes = nprobes or len(list(self.session_path.joinpath('raw_ephys_data').rglob('*.ap.bin')))
            match nprobes:
                case 1: stub_name = 'single_probe.yaml'
                case 2: stub_name = 'dual_probe.yaml'
            stub_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'neuropixel', stub_name)
            sync_file = Path(iblrig.__file__).parent.joinpath('device_descriptions', 'sync', 'nidq.yaml')
            acquisition_description = session_params.read_params(stub_file)
            acquisition_description.update(session_params.read_params(sync_file))
        super(EphysCopier, self).initialize_experiment(acquisition_description=acquisition_description, **kwargs)

    def _copy_collections(self):
        import ibllib.pipes.misc
        """
        Here we overload the copy to be able to rename the probes properly and also create the insertions
        :return:
        """
        log.info(f"Transferring ephys session: {self.session_path} to {self.remote_session_path}")
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
            log.info("Probe creation failed, please create the probe insertions manually. Continuing transfer...")
        return rsync_paths(self.session_path.joinpath('raw_ephys_data'), self.remote_session_path.joinpath('raw_ephys_data'))
