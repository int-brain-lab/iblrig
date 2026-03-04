import argparse
import logging
import re
from collections.abc import Sequence
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


def start_neurophotometrics_cli() -> None:
    # helper function that is registered in the pyproject.toml to be called from the command line
    args = _start_neurophotometrics_parser()
    debug_level = 'DEBUG' if args.debug else 'INFO'
    setup_logger(name='iblrig', level=debug_level)
    start_neurophotometrics(**vars(args))


def _start_neurophotometrics_parser() -> argparse.Namespace:
    # accompanying parser. Single use function, TODO to be removed
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
    # starts the neurophotometrics device / bonsai workflow

    # settings
    hardware_settings = iblrig.path_helper.load_pydantic_yaml(HardwareSettings)
    if hardware_settings.device_neurophotometrics is None:
        raise ValueError('device_neurophotometrics is not configured in hardware_settings.yaml')
    settings = hardware_settings.device_neurophotometrics
    iblrig_paths = iblrig.path_helper.get_local_and_remote_paths()

    # this defines where the data is stored stored on disk at acquisition
    datestr = datetime.now().strftime('%Y-%m-%d')
    timestr = datetime.now().strftime('T%H%M%S')
    folder_neurophotometrics = iblrig_paths['local_data_folder'] / 'neurophotometrics' / datestr / timestr
    _logger.info(f'Creating folder for neurophotometrics data: {folder_neurophotometrics}')
    folder_neurophotometrics.mkdir(parents=True, exist_ok=True)

    # depending on the sync mode: launch different bonsai workflows that are configured
    # for the respective synchronization modes
    match sync_mode:
        case 'bpod':
            bonsai_params = {
                'FileNamePhotometry': str(folder_neurophotometrics / 'raw_photometry.csv'),
                'FileNameDigitalInput': str(folder_neurophotometrics / 'digital_inputs.csv'),
                'PortName': settings.COM_NEUROPHOTOMETRY,
            }
            workflow_file = BASE_PATH.joinpath(settings.BONSAI_WORKFLOW)
        case 'daqami':
            # prompt user to start the DAQ
            input('Please start the DAQ recording and press Enter to continue...')

            # this will need to select an alternative workflow with different settings
            bonsai_params = {
                'FileNamePhotometry': str(folder_neurophotometrics / 'raw_photometry.csv'),
                'PortName': settings.COM_NEUROPHOTOMETRY,
            }
            workflow_file = BASE_PATH.joinpath(settings.BONSAI_WORKFLOW_DAQ)
        case _:
            raise NotImplementedError(f'Unknown sync mode: {sync_mode}')

    # launch bonsai
    call_bonsai(
        workflow_file=workflow_file,
        parameters=bonsai_params,
        bonsai_executable=settings.BONSAI_EXECUTABLE,
        start=False,
    )


def initialize_subject_cli() -> None:
    # helper function that is registered in the pyproject.toml to be called from the command line
    args = _initialize_subject_parser()
    debug_level = 'DEBUG' if args.debug else 'INFO'
    setup_logger(name='iblrig', level=debug_level)
    init_neurophotometrics_subject(**vars(args))


def _initialize_subject_parser() -> argparse.Namespace:
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
    subject: str,
    rois: Sequence[str],
    locations: Sequence[str],
    sync_channel: int = 1,
    sync_mode: Literal['bpod', 'daqami'] = 'bpod',
    **kwargs,
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
        The subject nickname.
    rois : Iterable[str]
        List of ROIs to be recorded.
    locations : Iterable[str]
        List of brain locations to be recorded.
    sync_channel : int, optional
        Channel to use for syncing photometry and digital inputs, by default 1
    sync_mode : {'bpod', 'daqami'}, optional
        Synchronization mode, by default 'bpod'.

    Returns
    -------
     NeurophotometricsCopier
        An instance of the NeurophotometricsCopier class initialized with the provided session details.
    """
    # generate acquisition description from input arguments
    acquisition_description = neurophotometrics_description(rois, locations, sync_channel, sync_mode=sync_mode)

    # constructing the stub name
    iblrig_paths = iblrig.path_helper.get_local_and_remote_paths()
    date = datetime.today().strftime('%Y-%m-%d')

    # counting the number of directories (to get the session number)
    # if this folder doesn't exist, it's the first session
    subject_date_folder = iblrig_paths['local_subjects_folder'] / subject / date
    subject_date_folder.mkdir(parents=True, exist_ok=True)

    # inferring session number
    folders = list(subject_date_folder.glob('*/'))
    # filter to only those folders that are three numbers (and nothing else)
    session_folders = [folder for folder in folders if re.fullmatch(r'\d{3}', folder.name) and folder.is_dir()]

    # this is continuously incrementing. A problem that UDP based communiction between the rigs and the
    # neurophotometrics computer can fix.
    n = len(session_folders)
    session_number = f'{n + 1:03}'
    stub_name = f'{subject}/{date}/{session_number}'

    # instantiating the copier - does not create folders on disk
    session_path = iblrig_paths['local_subjects_folder'] / stub_name
    copier = NeurophotometricsCopier(session_path=session_path, remote_subjects_folder=iblrig_paths['remote_subjects_folder'])

    # initializing the experiment - creates the folders
    copier.initialize_experiment(acquisition_description=acquisition_description)
    return copier


def _validate_neurophotometrics_description(
    rois: Sequence[str] | None = None,
    locations: Sequence[str] | None = None,
    sync_channel: int | None = None,
    sync_mode: Literal['bpod', 'daqami'] | None = None,
):
    """Helper function to validate the output of the CLI parser, or programmatic use."""
    if rois is None or locations is None or sync_channel is None or sync_mode is None:
        return
    # verify if brain regions are valid allen acronyms
    regions = BrainRegions()
    for location in locations:
        if location not in regions.acronym:
            _logger.warning(f'brain region {location} is not a valid Allen Acronym')

    # verify if sync channel is valid
    if sync_mode == 'bpod':
        assert sync_channel in (0, 1), 'sync channel must be either 0 or 1'
    if sync_mode == 'daqami':
        assert sync_channel in (1, 2, 3, 4, 5, 6), 'sync channel must be between 1 and 6 (DI0 is reserved for the frame clock)'

    # assert compatible shapes
    assert len(rois) == len(locations), 'The number of ROIs and locations must be the same.'
    assert len(set(rois)) == len(rois), 'duplicate rois are not possible'

    # assert each location being sampled at max twice and if so, by different bands
    for location in set(locations):
        ix = [i for i, loc in enumerate(locations) if loc == location]
        assert len(ix) <= 2, 'there are only 2 possible bands'
        rois_per_loc = [rois[i] for i in ix]
        # check that each band is present once or none
        assert sum(True for roi in rois_per_loc if roi.startswith('G')) in [0, 1], 'duplicate green band'
        assert sum(True for roi in rois_per_loc if roi.startswith('R')) in [0, 1], 'duplicate red band'
    assert sync_mode in ('bpod', 'daqami'), 'sync mode must be either bpod or daqami'


def neurophotometrics_description(
    rois: Sequence[str],
    locations: Sequence[str],
    sync_channel: int,
    start_time: datetime | None = None,
    sync_label: str | None = None,
    sync_mode: Literal['bpod', 'daqami'] = 'bpod',
    collection: str = 'raw_photometry_data',
    validate: bool = True,
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
    sync_mode : {'bpod', 'daqami'}, optional
        Defines the sync mode: 'bpod' uses FP3002 digital inputs for sync; 'daqami' uses a DAQ to record frame times.

    Returns
    -------
    dict
        Description of the neurophotometrics data


    Example where bpod sends sync to the neurophotometrics:
    -------
        neurophotometrics:
            fibers:
                G0:
                    location: VTA
                G1:
                    location: DR
            collection: raw_photometry_data
            sync_label: bnc1out
            sync_channel: 1
            datetime: 2024-09-19T14:13:18.749259
            sync_mode: bpod


    Example where a DAQ records frame times and sync:
    -------
        neurophotometrics:
            fibers:
                G0:
                    location: VTA
                G1:
                    location: DR
            collection: raw_photometry_data
            sync_channel: 1
            datetime: 2024-09-19T14:13:18.749259
            sync_mode: daqami
            sync_metadata:
                acquisition_software: daqami
                collection: raw_photometry_data
                frameclock_channel: 0

    """
    if validate:
        _validate_neurophotometrics_description(rois=rois, locations=locations, sync_channel=sync_channel, sync_mode=sync_mode)

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

    match sync_mode:
        case 'bpod':
            return {'devices': {'neurophotometrics': description}}
        case 'daqami':
            hardware_settings = iblrig.path_helper.load_pydantic_yaml(HardwareSettings)
            if hardware_settings.device_neurophotometrics is None:
                raise ValueError('device_neurophotometrics is not configured in hardware_settings.yaml')
            settings = hardware_settings.device_neurophotometrics
            experiment_description = {'devices': {'neurophotometrics': description}}
            experiment_description['devices']['neurophotometrics']['sync_metadata'] = dict(
                acquisition_software='daqami',
                collection='raw_photometry_data',
                frameclock_channel=settings.FRAMECLOCK_CHANNEL,
            )
            return experiment_description
        case _:
            raise NotImplementedError(f'unknown sync mode {sync_mode}')
