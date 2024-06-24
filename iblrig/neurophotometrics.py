import argparse
import datetime
import logging
from pathlib import Path

from iblutil.util import setup_logger
import iblrig
from iblrig.tools import call_bonsai
import iblrig.path_helper

from iblrig.pydantic_definitions import HardwareSettings

_logger = logging.getLogger(__name__)


def start_workflow(debug: bool = False):
    # TODO docstring
    # format the current date and time as a standard string
    datestr = datetime.datetime.now().strftime('%Y-%m-%d')
    timestr = datetime.datetime.now().strftime('T%H%M%S')
    dict_paths = iblrig.path_helper.get_local_and_remote_paths()
    folder_neurophotometrics = dict_paths['local_data_folder'].joinpath('neurophotometrics', datestr, timestr)
    _logger.info(f'Creating folder for neurophotometrics data: {folder_neurophotometrics}')
    bonsai_params = {
        'FileNamePhotometry': str(folder_neurophotometrics.joinpath('raw_photometry.csv')),
    }
    hardware_settings = iblrig.path_helper.load_pydantic_yaml(HardwareSettings)
    # workflow_file = Path(iblrig.__file__).parents[1].joinpath(hardware_settings['device_neurophotometrics']['BONSAI_WORKFLOW'])
    call_bonsai(
        workflow_file=Path(iblrig.__file__).parents[1].joinpath('devices', 'neurophotometrics', 'FP3002.bonsai'),
        parameters=bonsai_params,
        bonsai_executable=Path(r"C:\Users\IBLuser\AppData\Local\Bonsai\Bonsai.exe"),
    )


def init_neurophotometrics_session():
    # TODO this needs to link the session (subject/date/number) to a photometry recording
    # copier = NeurophotometricsCopier(session_path=session_path, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
    # copier.initialize_experiment(acquisition_description=copier.config2stub(config, raw_data_folder.name))
    pass


def start_workflow_cmd():
    """
    Command line interface for preparing a neurophotometrics session on the photometry computer
    :return:
    """
    parser = argparse.ArgumentParser(prog='start_photometry_recording',
                                     description='Prepare photometry computer PC for recording session.')
    parser.add_argument('--debug', action='store_true', help='enable debugging mode')
    args = parser.parse_args()
    setup_logger(name='iblrig', level='DEBUG' if args.debug else 'INFO')
    start_workflow(debug=args.debug)
