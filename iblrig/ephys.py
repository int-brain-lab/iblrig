import argparse
import string

import numpy as np

from iblatlas import atlas
from iblrig.base_tasks import EmptySession
from iblrig.transfer_experiments import EphysCopier
from iblutil.util import setup_logger


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
    copier = EphysCopier(session_path=session_path, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
    copier.initialize_experiment(nprobes=nprobes)


def neuropixel24_micromanipulator_coordinates(ref_shank, pname, ba=None, shank_spacings_um=(0, 200, 400, 600)):
    """
    Provide the micro-manipulator coordinates of the first shank.

    This function returns the relative coordinates of all shanks, labeled as probe01a, probe01b, etc.

    :param ref_shank: dictionary with keys x, y, z, phi, theta, depth, roll
    example: {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
    :param pname: str
    :param ba: brain atlas object
    :param shank_spacings_um: list of shank spacings in micrometers
    :return:
    """
    # this only works if the roll is 0, ie. the probe is facing upwards
    assert ref_shank['roll'] == 0
    ba = atlas.NeedlesAtlas() if ba is None else ba
    trajectories = {}
    for i, d in enumerate(shank_spacings_um):
        x = ref_shank['x'] + np.sin(ref_shank['phi'] / 180 * np.pi) * d
        y = ref_shank['y'] - np.cos(ref_shank['phi'] / 180 * np.pi) * d
        shank = {
            'x': x,
            'y': y,
            'z': np.nan,
            'phi': ref_shank['phi'],
            'theta': ref_shank['theta'],
            'depth': ref_shank['depth'],
            'roll': 0,
        }
        insertion = atlas.Insertion.from_dict(shank, brain_atlas=ba)
        xyz_entry = atlas.Insertion.get_brain_entry(insertion.trajectory, ba)
        if i == 0:
            xyz_ref = xyz_entry
        shank['z'] = xyz_entry[2] * 1e6
        shank['depth'] = ref_shank['depth'] + (xyz_entry[2] - xyz_ref[2]) * 1e6
        trajectories[f'{pname}{string.ascii_lowercase[i]}'] = shank
    return trajectories
