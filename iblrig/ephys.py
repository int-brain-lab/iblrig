import argparse

import numpy as np

from iblatlas import atlas
from ibllib.ephys.spikes import create_insertion
from iblrig.base_tasks import EmptySession
from iblrig.transfer_experiments import EphysCopier
from iblutil.util import setup_logger
from one.webclient import no_cache as no_cache_context


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


def neuropixel24_micromanipulator_coordinates(
    ref_shank: dict,
    pname: str,
    ba: atlas.BrainAtlas | None = None,
    shank_spacings_um: tuple[float, ...] = (0, 250, 500, 750),
    shank_order: str = 'abcd',
) -> dict[str, dict]:
    """
    Calculate micro-manipulator coordinates for all shanks of a Neuropixel 2.4 probe based on a reference shank.

    This function computes the spatial coordinates for each shank of a multi-shank Neuropixel 2.4 probe
    relative to a reference shank. It accounts for the physical spacing between shanks and calculates
    the brain entry points and depths for each shank using a brain atlas. The shanks are labeled with
    letters (a, b, c, d) appended to the probe name.

    Parameters
    ----------
    ref_shank : dict
        Dictionary containing the reference shank coordinates with the following keys:
        - 'x' : float
            Lateral position in micrometers
        - 'y' : float
            Anterior-posterior position in micrometers
        - 'z' : float
            Dorsal-ventral position in micrometers
        - 'phi' : float
            Azimuth angle in degrees (rotation around z-axis)
        - 'theta' : float
            Polar angle in degrees (tilt from vertical)
        - 'depth' : float
            Insertion depth in micrometers
        - 'roll' : float
            Roll angle in degrees
        Example: {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
    pname : str
        Base name for the probe (e.g., 'probe01'). Shank letters will be appended to this name in multi-shanks situations
    ba : atlas.BrainAtlas, optional
        Brain atlas object used for coordinate transformations and brain entry calculations.
        If None, a iblatlas.atlas.BrainAtlas instance will be created. Default is None.
    shank_spacings_um : tuple of float, optional
        Spacing distances in micrometers for each shank relative to the reference shank.
        Default is (0, 250, 500, 750) for a 4-shank probe.
    pivot_shank : str, optional
        Specifies which shank is the reference ('a' or 'd'). If 'a', shanks are ordered a→b→c→d
        with increasing spacing. If 'd', shanks are ordered d→c→b→a with decreasing spacing.
        Default is 'a'.

    Returns
    -------
    dict
        Dictionary mapping shank names to their coordinate dictionaries. Each key is a string
        combining the probe name with a shank letter (e.g., 'probe01a', 'probe01b'). Each value
        is a dictionary containing the calculated coordinates with keys: 'x', 'y', 'z', 'phi',
        'theta', 'depth', and 'roll'.

    Raises
    ------
    ValueError
        If pivot_shank is not 'a' or 'd'.
    """
    ref_shank['roll'] = 0
    assert shank_order in ('abcd', 'dcba'), "reference_shank parameter should be either 'abcd' or 'dcba'"

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
        trajectories[f'{pname}{shank_order[i]}'] = shank
    return trajectories


def register_micromanipulator_coordinates(
    alyx, eid: str, trajectories: dict[str, dict] | None = None, metadata: dict | None = None
) -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Register micro-manipulator coordinates for probe trajectories in the Alyx database.

    This function creates or updates probe insertion and trajectory records in Alyx based on
    micro-manipulator coordinates. For each probe trajectory, it creates a probe insertion
    record and associates it with a trajectory record containing the spatial coordinates.
    If a trajectory already exists for a given probe insertion, it updates the existing record;
    otherwise, it creates a new one.

    Parameters
    ----------
    alyx : one.webclient.AlyxClient
        An authenticated Alyx client instance used to communicate with the Alyx REST API.
    eid : str
        Experiment ID (session UUID) to which the probe insertions belong.
    trajectories : dict of str to dict, optional
        Dictionary mapping probe names to their trajectory coordinate dictionaries.
        Each trajectory dictionary should contain keys such as 'x', 'y', 'z', 'phi',
        'theta', 'depth', and 'roll'. If None, an empty dictionary is used. Default is None.
    metadata : dict, optional
        Metadata dictionary for the probe insertion containing information such as
        'neuropixelVersion', 'fileName', and 'serial'. If None, defaults to
        {'neuropixelVersion': 'NP2.4', 'fileName': None, 'serial': -1}. Default is None.

    Returns
    -------
    tuple of (dict, dict)
        A tuple containing two dictionaries:
        - rest_insertions : dict
            Dictionary mapping probe names to their created probe insertion records from Alyx.
        - rest_trajectories : dict
            Dictionary mapping probe names to their created or updated trajectory records from Alyx.
    """
    # if we do not have access to the fileName or any of the metadata, it will be patched later
    metadata = {'neuropixelVersion': 'NP2.4', 'fileName': None, 'serial': -1} if metadata is None else metadata
    rest_trajectories = {}
    rest_insertions = {}
    with no_cache_context(alyx):
        traj_extra = {}
        for pname, traj in trajectories.items():
            _, rest_insertions[pname] = create_insertion(alyx, metadata, pname, eid=eid)
            pid = rest_insertions[pname]['id']
            traj_extra['probe_insertion'] = pid
            traj_extra['chronic_insertion'] = None
            traj_extra['provenance'] = 'Micro-manipulator'
            traj_extra['coordinate_system'] = 'Needles-Allen'
            rest_trajectory = alyx.rest('trajectories', 'list', probe_insertion=pid, provenance='Micro-manipulator')
            if len(rest_trajectory) == 0:
                rest_trajectories[pname] = alyx.rest('trajectories', 'create', data=traj | traj_extra)
            else:
                rest_trajectories[pname] = alyx.rest(
                    'trajectories', 'update', id=rest_trajectory[0]['id'], data=traj | traj_extra
                )
    return rest_insertions, rest_trajectories
