import argparse
from datetime import datetime
import logging
from collections.abc import Iterable

import iblrig.path_helper
from iblatlas.atlas import BrainRegions
from iblrig.constants import BASE_PATH
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.tools import call_bonsai
from iblrig.transfer_experiments import NeurophotometricsCopier
from iblutil.util import setup_logger
from typing import Literal
import re

_logger = logging.getLogger(__name__)


def start_workflow_cmd(debug: bool = False, sync: Literal['bpod', 'daqami'] = 'bpod'):
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

    match sync:
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
            raise NotImplementedError


def init_neurophotometrics_subject(
    subject: str, rois: Iterable[str], locations: Iterable[str], sync_channel: int = 1, **kwargs
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
    description = NeurophotometricsCopier.neurophotometrics_description(rois, locations, sync_channel, **kwargs)
    # this does
    copier.initialize_experiment(acquisition_description=description)
    return copier


def start_photometry_task_cmd():
    """
    Command line interface for preparing a neurophotometrics session on the photometry computer.
    start_photometry_task --subject Mickey --rois G0 G1 --location NBM SI
    :return:
    """
    parser = argparse.ArgumentParser(
        prog='start_photometry_recording', description='Prepare photometry computer PC for recording session.'
    )
    parser.add_argument('-s', '--subject', type=str, required=True, help='Subject name')
    parser.add_argument(
        '-r', '--rois', nargs='+', type=str, required=True, help='Define ROI(s). Separate multiple values by spaces.'
    )
    parser.add_argument(
        '-l',
        '--locations',
        nargs='+',
        type=str,
        required=True,
        help='Location of Fiber(s). Separate multiple values by spaces. Usually Allen brain acronyms.',
    )
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debugging mode')
    parser.add_argument('-c', '--sync-channel', type=int, default=1, help='Sync channel')
    args = parser.parse_args()

    assert len(args.rois) == len(args.locations), 'The number of ROIs and locations must be the same.'
    assert len(set(args.rois)) == len(args.rois), 'duplicate rois are not possible'
    # TODO docme and the rationale behind this - will be subject of DAWG meeting
    band = 'G' if any([roi.startswith('G') for roi in args.rois]) else 'R'
    ix = [i for i, roi in enumerate(args.rois) if roi.startswith(band)]
    locations = [args.locations[i] for i in ix]
    assert len(set(locations)) == len(locations), 'duplicate brain regions are not possible'

    setup_logger(name='iblrig', level='DEBUG' if args.debug else 'INFO')
    init_neurophotometrics_subject(subject=args.subject, rois=args.rois, locations=args.locations, sync_channel=args.sync_channel)
