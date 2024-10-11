import argparse
import datetime
import logging
from collections.abc import Iterable

import iblrig.path_helper
from iblrig.constants import BASE_PATH
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.tools import call_bonsai
from iblutil.util import setup_logger

_logger = logging.getLogger(__name__)


def start_workflow_cmd(debug: bool = False):
    """
    Start a photometry recording regardless of behaviour.
    """
    # format the current date and time as a standard string
    hardware_settings: HardwareSettings = iblrig.path_helper.load_pydantic_yaml(HardwareSettings)
    settings = hardware_settings.device_neurophotometrics
    datestr = datetime.datetime.now().strftime('%Y-%m-%d')
    timestr = datetime.datetime.now().strftime('T%H%M%S')
    dict_paths = iblrig.path_helper.get_local_and_remote_paths()
    folder_neurophotometrics = dict_paths['local_data_folder'].joinpath('neurophotometrics', datestr, timestr)
    bonsai_params = {
        'FileNamePhotometry': str(folder_neurophotometrics.joinpath('raw_photometry.csv')),
        'FileNameDigitalInput': str(folder_neurophotometrics.joinpath('digital_inputs.csv')),
        'PortName': settings.COM_NEUROPHOTOMETRY,
    }
    _logger.info(f'Creating folder for neurophotometrics data: {folder_neurophotometrics}')
    folder_neurophotometrics.mkdir(parents=True, exist_ok=True)
    workflow_file = BASE_PATH.joinpath(settings.BONSAI_WORKFLOW)
    call_bonsai(
        workflow_file=workflow_file,
        parameters=bonsai_params,
        bonsai_executable=settings.BONSAI_EXECUTABLE,
        start=False,
    )


def init_neurophotometrics_session(subject: str, rois: Iterable[str], locations: Iterable[str], sync_channel: int = 1):
    # TODO this needs to link the session (subject/date/number) to a photometry recording
    # this means
    # 1) link from one session to possibly several regions (ie. columns of the datafile)
    # 2) link one session to a digital input number
    # we use a single entry point for both modes of acquisition (ie. with or without a daq)

    # first read in the columns name from the photometry file
    # then locate the sessions acquired from the same day on the local server
    # for the case without a DAQ
    #   at last the digital input is hardcoded from input1 input0
    # for the case with a DAQ
    #   we need a hardware setting linking the rig name to a daq channel
    #   we get the rig name from the stub file on the server / UDP or ask for it in the GUI

    # copier = NeurophotometricsCopier(session_path=session_path, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
    # copier.initialize_experiment(acquisition_description=copier.config2stub(config, raw_data_folder.name))
    pass


def start_photometry_task_cmd():
    """
    Command line interface for preparing a neurophotometrics session on the photometry computer.
    start_photometry_recording -s Algernon --rois G0 G1 --locations
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

    assert len(args.roi) == len(args.location), 'The number of ROIs and locations must be the same.'

    setup_logger(name='iblrig', level='DEBUG' if args.debug else 'INFO')
    init_neurophotometrics_session(subject=args.subject, rois=args.roi, locations=args.location, sync_channel=args.sync_channel)
