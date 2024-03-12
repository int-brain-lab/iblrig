import argparse
from iblrig.base_tasks import EmptySession

from iblutil.util import setup_logger
from iblrig.transfer_experiments import EphysCopier


def prepare_ephys_session_cmd():
    parser = argparse.ArgumentParser(prog='start_video_session', description='Prepare video PC for video recording session.')
    parser.add_argument('subject_name', help='name of subject')
    parser.add_argument('nprobes', help='number of probes', type=int, default=2)
    parser.add_argument('--debug', action='store_true', help='enable debugging mode')
    args = parser.parse_args()
    setup_logger(name='iblrig', level='DEBUG' if args.debug else 'INFO')
    prepare_ephys_session(args.subject_name, args.nprobes)


def prepare_ephys_session(subject_name: str, nprobes: int = 2):
    """
    Setup electrophysiology recordings.

    Parameters
    ----------
    subject_name : str
        A subject name.
    nprobes : int
        Number of probes to be used
    """

    # Initialize a session for paths and settings
    session = EmptySession(subject=subject_name, interactive=False)
    session_path = session.paths.SESSION_FOLDER
    copier = EphysCopier(session_path)
    copier.initialize_experiment(nprobes=nprobes)
