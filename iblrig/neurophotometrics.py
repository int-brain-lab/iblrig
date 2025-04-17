import argparse
import logging
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Literal

import iblrig.path_helper
from iblatlas.atlas import BrainRegions
from iblrig.constants import BASE_PATH
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.tools import call_bonsai
from iblrig.transfer_experiments import NeurophotometricsCopier
from iblutil.util import setup_logger

_logger = logging.getLogger(__name__)


def start_neurophotometrics_cli():
    args = _start_neurophotometrics_parser('start the neurophotometrics device')
    debug_level = 'DEBUG' if args.debug else 'INFO'
    setup_logger(name='iblrig', level=debug_level)
    start_neurophotometrics(**vars(args))


def _start_neurophotometrics_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='neurophotometrics',
        description='initialize neurophotometrics FP3002 device',
    )
    parser.add_argument(
        '-m',
        '--sync_mode',
        type=str,
        required=True,
        help='sync mode, must be either bpod or daqami',
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='Enable debug output',
    )
    # Parse the arguments
    return parser.parse_args()


def start_neurophotometrics(debug: bool = False, sync_mode: Literal['bpod', 'daqami'] = 'bpod'):
    """
    Start a photometry recording regardless of behaviour.
    This should happen before the neurophotometrics recording has been started.
    """
    hardware_settings: HardwareSettings = iblrig.path_helper.load_pydantic_yaml(HardwareSettings)
    settings = hardware_settings.device_neurophotometrics
    # format the current date and time as a standard string
    datestr = datetime.now().strftime('%Y-%m-%d')
    timestr = datetime.now().strftime('T%H%M%S')
    iblrig_paths = iblrig.path_helper.get_local_and_remote_paths()
    # this defines the way how the data is stored stored on disk at acquisition
    # note that this is not taken into account by the neurophotometrics node, as it stored the raw_photometry file
    # in a subfolder if it also exports the snapshot of the bundle
    # also note that this is going to change if DAQ based synchronization scheme is applied,
    # as there are no digital inputs (rather the BNC is used as a digital output of the frametrigger / clock)
    folder_neurophotometrics = (
        iblrig_paths['local_data_folder'] / 'neurophotometrics' / datestr / timestr
    )  # this here also defines where the neurophotometrics data is stored
    _logger.info(f'Creating folder for neurophotometrics data: {folder_neurophotometrics}')
    folder_neurophotometrics.mkdir(parents=True, exist_ok=True)

    match sync_mode:
        case 'bpod':
            bonsai_params = {
                'FileNamePhotometry': str(folder_neurophotometrics / 'raw_photometry.csv'),
                'FileNameDigitalInput': str(folder_neurophotometrics / 'digital_inputs.csv'),
                'PortName': settings.COM_NEUROPHOTOMETRY,
            }
            workflow_file = BASE_PATH.joinpath(settings.BONSAI_WORKFLOW)
            call_bonsai(
                workflow_file=workflow_file,
                parameters=bonsai_params,
                bonsai_executable=settings.BONSAI_EXECUTABLE,
                start=False,
            )
        case 'daqami':
            # this will need to select an alternative workflow with different settings
            bonsai_params = {
                'FileNamePhotometry': str(folder_neurophotometrics / 'raw_photometry.csv'),
                'PortName': settings.COM_NEUROPHOTOMETRY,
            }
            workflow_file = BASE_PATH.joinpath(settings.BONSAI_WORKFLOW_DAQ)
            call_bonsai(
                workflow_file=workflow_file,
                parameters=bonsai_params,
                bonsai_executable=settings.BONSAI_EXECUTABLE,
                start=False,
            )


def initialize_subject_cli():
    args = _initialize_subject_parser()
    debug_level = 'DEBUG' if args.debug else 'INFO'
    setup_logger(name='iblrig', level=debug_level)
    init_neurophotometrics_subject(**vars(args))


def _initialize_subject_parser() -> argparse.ArgumentParser:
    """
    Command line interface for preparing a neurophotometrics session on the photometry computer.
    start_photometry_task --subject Mickey --rois G0 G1 --location NBM SI
    :return:
    """
    parser = argparse.ArgumentParser(
        prog='start_photometry_recording',
        description='Prepare photometry computer PC for recording session.',
    )
    parser.add_argument(
        '-s',
        '--subject',
        type=str,
        required=True,
        help='Subject name',
    )
    parser.add_argument(
        '-r',
        '--rois',
        nargs='+',
        type=str,
        required=True,
        help='Define ROI(s). Separate multiple values by spaces.',
    )
    parser.add_argument(
        '-l',
        '--locations',
        nargs='+',
        type=str,
        required=True,
        help='Location of Fiber(s). Separate multiple values by spaces. Usually Allen brain acronyms.',
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='Enable debugging mode',
    )
    parser.add_argument(
        '-c',
        '--sync-channel',
        type=int,
        default=1,
        help='Sync channel',
    )
    parser.add_argument(
        '-m',
        '--sync-mode',
        type=str,
        default='bpod',
        help='defines the sync mode. Must be either bpod or daqami',
    )
    return parser.parse_args()


def init_neurophotometrics_subject(
    subject: str, rois: Iterable[str], locations: Iterable[str], sync_channel: int = 1, sync_mode='bpod', **kwargs
) -> NeurophotometricsCopier:
    """
    Initialize a neurophotometrics behavior session.
    This should happen after the neurophotometrics recording has been started.
    - Creates a new folder for the session on the photometry computer.
    - Creates a new experiment description file in the session folder.
    - Copies the experiment description stub to the server

    Parameters
    ----------
    subject : str
        The name of the session_stub for this session.
    rois : Iterable[str]
        List of ROIs to be recorded.
    locations : Iterable[str]
        List of brain locations to be recorded.
    sync_channel : int, optional
        Channel to use for syncing photometry and digital inputs, by default 1
    kwargs : dict, optional
        Additional keyword arguments to be passed to the NeurophotometricsCopier.neurophotometrics_description method.

    Returns
    -------
     NeurophotometricsCopier
        An instance of the NeurophotometricsCopier class initialized with the provided session details.
    """
    # I put the import here as it may slow down
    regions = BrainRegions()
    if not all(map(lambda x: x in regions.acronym, locations)):
        _logger.warning(f'Brain regions {locations} not found in BrainRegions acronyms')

    # constructing the stub name
    iblrig_paths = iblrig.path_helper.get_local_and_remote_paths()
    date = datetime.today().strftime('%Y-%m-%d')

    # counting the number of directories (to get the session number)
    # if this folder doesn't exist, it's the first session
    subject_date_folder = iblrig_paths['local_subjects_folder'] / subject / date
    subject_date_folder.mkdir(parents=True, exist_ok=True)

    # inferring session number
    folders = subject_date_folder.glob('*/')
    # filter to only those folders that are three numbers (and nothing else)
    session_folders = [folder for folder in folders if re.match(r'^\d{3}$', folder) and folder.is_dir()]

    # this is continuously incrementing. A problem
    n = len(session_folders)
    session_number = f'{n + 1:03}'
    stub_name = f'{subject}/{date}/{session_number}'

    # creating the copier from the stub name and initializing
    session_path = iblrig_paths['local_subjects_folder'] / stub_name
    # instantiating the copier - does not create folders on disk
    copier = NeurophotometricsCopier(session_path=session_path, remote_subjects_folder=iblrig_paths['remote_subjects_folder'])
    acquisition_description = neurophotometrics_description(rois, locations, sync_channel, sync_mode=sync_mode, **kwargs)
    # this does
    copier.initialize_experiment(acquisition_description=acquisition_description)
    return copier


def verify_init_arguments(
    subject=None,
    rois=None,
    locations=None,
    sync_channel=None,
    sync_mode=None,
):
    """Helper function to validate the output of the CLI parser, or programmatic u

    Args:
        subject (_type_, optional): _description_. Defaults to None.
        rois (_type_, optional): _description_. Defaults to None.
        locations (_type_, optional): _description_. Defaults to None.
        sync_channel (_type_, optional): _description_. Defaults to None.
        sync_mode (_type_, optional): _description_. Defaults to None.
    """
    assert len(rois) == len(locations), 'The number of ROIs and locations must be the same.'
    assert len(set(rois)) == len(rois), 'duplicate rois are not possible'
    # TODO docme and the rationale behind this - will be subject of DAWG meeting
    band = 'G' if any([roi.startswith('G') for roi in rois]) else 'R'
    ix = [i for i, roi in enumerate(rois) if roi.startswith(band)]
    locations = [locations[i] for i in ix]
    assert len(set(locations)) == len(locations), 'duplicate brain regions are not possible'
    assert sync_mode in ('bpod', 'daqami'), 'sync mode must be either bpod or daqami'


def neurophotometrics_description(
    rois: Iterable[str],
    locations: Iterable[str],
    sync_channel: int,
    start_time: datetime = None,
    sync_label: str = None,
    sync_mode: str = 'bpod',
    collection: str = 'raw_photometry_data',
) -> dict:
    """
    Create the `neurophotometrics` description part for the specified parameters.

    Parameters
    ----------
    rois: list of strings
        List of ROIs
    locations: list of strings
        List of brain regions
    sync_channel: int
        Channel number for sync
    start_time: datetime.datetime, optional
        Date and time of the recording
    sync_label: str, optional
        Label for the sync channel
    sync_mode, str, opional
        defines the sync mode (e.g. using the FP3002 inputs as sync inputs, or as outputs to sync the DAQ)

    Returns
    -------
    dict
        Description of the neurophotometrics data
        {neurophotometrics': ...}, see below for the yaml rendition of dictionaries


    Example where bpod sends sync to the neurophotometrics:
    -------
        neurophotometrics:
            fibers:
            - roi: G0
                location: VTA
            - roi: G1
                location: DR
            collection: raw_photometry_data
            sync_label: bnc1out
            sync_channel: 1
            datetime: 2024-09-19T14:13:18.749259
            sync_mode: bpod
        sync:
            bpod

    Here MAIN_SYNC=True on behaviour

    Example where a DAQ records frame times and sync:
    -------
        neurophotometrics:
            fibers:
            - roi: G0
                location: VTA
            - roi: G1
                location: DR
            collection: raw_photometry_data
            sync_channel: 5
            datetime: 2024-09-19T14:13:18.749259
            sync_mode: daqami
        sync:
            daqami:
                acquisition_software: daqami
                collection: raw_sync_data
                extension: bin
    """
    # verify arguments first
    verify_init_arguments(rois=rois, locations=locations, sync_mode=sync_mode)

    # generate description
    date_time = datetime.now() if start_time is None else start_time
    description = {
        'sync_channel': sync_channel,
        'datetime': date_time.isoformat(),
        'collection': collection,
        'sync_mode': sync_mode,
    }
    # optionally set the sync label
    if sync_label is not None:
        description['sync_label'] = sync_label
    description['fibers'] = {roi: {'location': location} for roi, location in zip(rois, locations, strict=False)}
    return {'devices': {'neurophotometrics': description}}
