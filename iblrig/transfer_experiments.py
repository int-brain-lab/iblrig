from pathlib import Path
import traceback

from one.alf.files import filename_parts
from iblutil.util import setup_logger
from ibllib.io import session_params
from ibllib.pipes.misc import rsync_paths
import deploy.ephyspc
import deploy.videopc

log = setup_logger('iblrig', level='INFO')


class SessionCopier():
    tag = 'behavior'

    def __init__(self, session_path, remote_subjects_folder=None):
        self.session_path = Path(session_path)
        self.remote_subjects_folder = Path(remote_subjects_folder) if remote_subjects_folder else None
        self.experiment_description = session_params.read_params(self.session_path)
        self.remote_experiment_description_stub = session_params.read_params(self.session_path)

    def __repr__(self):
        return f"{super(SessionCopier, self).__repr__()} \n local: {self.session_path} \n remote: {self.remote_session_path}"

    def get_copy_state(self):
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
                self.remote_session_path, filename_parts(self.file_experiment_description.name)[3])

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
            status &= rsync_paths(local_collection, self.remote_session_path.joinpath(collection))
        return status

    def copy_collections(self):
        """
        Recursively copies the collection folders into the remote session path
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
        if not acquisition_description:
            return

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
                remote_stub_file.with_suffix('.status_pending').touch()
                log.info(f'Written data to remote device at: {remote_stub_file}.')
            except Exception as ex:
                log.warning(f'Failed to write data to remote device at: {remote_stub_file}. \n {ex}')

        # then create on the local machine
        previous_description = session_params.read_params(self.file_experiment_description)\
            if self.file_experiment_description.exists() and not overwrite else {}
        session_params.write_yaml(
            self.file_experiment_description, session_params.merge_params(previous_description, acquisition_description))
        log.info(f'Written data to local session at : {self.file_experiment_description}.')


class VideoCopier(SessionCopier):
    tag = 'video'

    def initialize_experiment(self, acquisition_description=None, **kwargs):
        if not acquisition_description:
            stub_file = Path(deploy.videopc.__file__).parent.joinpath('device_stubs', 'cameras_body_left_right.yaml')
            acquisition_description = session_params.read_params(stub_file)
        super(VideoCopier, self).initialize_experiment(acquisition_description=acquisition_description, **kwargs)


class EphysCopier(SessionCopier):
    tag = 'spikeglx'

    def initialize_experiment(self, acquisition_description=None, nprobes=None, **kwargs):
        if not acquisition_description:
            nprobes = nprobes or len(list(self.session_path.joinpath('raw_ephys_data').rglob('*.ap.bin')))
            match nprobes:
                case 1: stub_name = 'neuropixel_single_probe.yaml'
                case 2: stub_name = 'neuropixel_dual_probe.yaml'
            stub_file = Path(deploy.ephyspc.__file__).parent.joinpath('device_stubs', stub_name)
            acquisition_description = session_params.read_params(stub_file)
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
        path_wiring = Path(deploy.ephyspc.__file__).parent.joinpath('wirings')
        probe_model = '3A'
        for file_nidq_bin in self.session_path.joinpath('raw_ephys_data').glob('*.nidq.bin'):
            probe_model = '3B'
            import shutil
            shutil.copy(path_wiring.joinpath('nidq.wiring.json'), file_nidq_bin.with_suffix('.wiring.json'))
        for file_ap_bin in self.session_path.joinpath('raw_ephys_data').rglob('*.ap.bin'):
            shutil.copy(path_wiring.joinpath(f'{probe_model}.wiring.json'), file_ap_bin.with_suffix('.wiring.json'))
        try:
            ibllib.pipes.misc.create_alyx_probe_insertions(self.session_path)
        except BaseException:
            log.error(traceback.print_exc())
            log.info("Probe creation failed, please create the probe insertions manually. Continuing transfer...")
        return rsync_paths(self.session_path.joinpath('raw_ephys_data'), self.remote_session_path.joinpath('raw_ephys_data'))
