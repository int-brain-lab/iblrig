import argparse
import asyncio
import logging
import string
from pathlib import Path

import numpy as np

from iblatlas import atlas
from iblrig.base_tasks import EmptySession
from iblrig.net import get_server_communicator, read_stdin, update_alyx_token
from iblrig.transfer_experiments import EphysCopier
from iblutil.io import net
from iblutil.util import setup_logger
from one.api import OneAlyx


def prepare_ephys_session_cmd():
    parser = argparse.ArgumentParser(prog='start_video_session', description='Prepare video PC for video recording session.')
    parser.add_argument('subject_name', help='name of subject')
    parser.add_argument('nprobes', help='number of probes', type=int, default=2)
    parser.add_argument('--debug', action='store_true', help='enable debugging mode')
    parser.add_argument(
        '--service-uri',
        required=False,
        nargs='?',
        default=False,
        type=str,
        help='the service URI to listen to messages on. pass ":<port>" to specify port only.',
    )
    args = parser.parse_args()
    setup_logger(name=__name__, level='DEBUG' if args.debug else 'INFO')
    if args.service_uri:
        asyncio.run(main_v8_networked(args.subject_name, args.debug, args.nprobes, args.service_uri))
    else:
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


async def main_v8_networked(mouse, debug=False, n_probes=2, service_uri=None):
    log = logging.getLogger(__name__)

    session = EmptySession(subject=mouse, interactive=False)
    session_path = session.paths.SESSION_FOLDER
    raw_data_folder = session_path.joinpath('raw_ephys_data')

    # Save the stub files locally and in the remote repo for future copy script to use
    copier = EphysCopier(session_path=session_path, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
    communicator, _ = await get_server_communicator(service_uri, 'neuropixel')
    copier.initialize_experiment(nprobes=n_probes)

    one = OneAlyx(silent=True)
    exp_ref = one.path2ref(session_path)
    tasks = set()

    log.info('Type "abort" to cancel or just press return to finalize')
    while True:
        # Ensure we are awaiting a message from the remote rig.
        # This task must be re-added each time a message is received.
        if not any(t.get_name() == 'remote' for t in tasks) and communicator and communicator.is_connected:
            task = asyncio.create_task(communicator.on_event(net.base.ExpMessage.any()), name='remote')
            tasks.add(task)
        if not any(t.get_name() == 'keyboard' for t in tasks):
            tasks.add(asyncio.create_task(anext(read_stdin()), name='keyboard'))
        # Await the next task outcome
        done, _ = await asyncio.wait(tasks, timeout=None, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            match task.get_name():
                case 'keyboard':
                    if net.base.is_success(task):
                        line = task.result().strip().lower()
                        if line == 'abort' and not any(filter(Path.is_file, raw_data_folder.rglob('*'))):
                            log.warning('Removing %s', raw_data_folder)
                            for d in raw_data_folder.iterdir():  # Remove probe folders
                                d.rmdir()
                            raw_data_folder.rmdir()  # remove collection
                            # Remove remote exp description file
                            log.debug('Removing %s', copier.file_remote_experiment_description)
                            copier.file_remote_experiment_description.unlink()
                            copier.file_remote_experiment_description.with_suffix('.status_pending').unlink()
                            # Delete whole session folder?
                            session_files = list(session_path.rglob('*'))
                            if len(session_files) == 1 and session_files[0].name.startswith('_ibl_experiment.description'):
                                ans = input(f'Remove empty session {"/".join(session_path.parts[-3:])}? [y/N]\n')
                                if (ans.strip().lower() or 'n')[0] == 'y':
                                    log.warning('Removing %s', session_path)
                                    log.debug('Removing %s', session_files[0])
                                    session_files[0].unlink()
                                    session_path.rmdir()
                        else:
                            session_path.joinpath('transfer_me.flag').touch()
                        communicator.close()
                        for t in tasks:
                            t.cancel()
                        tasks.clear()
                        return
                case 'remote':
                    if task.cancelled():
                        log.debug('Remote com await cancelled')
                        log.error('Remote communicator closed')
                    else:
                        data, addr, event = task.result()
                        S = net.base.ExpMessage  # noqa
                        match event:
                            case S.EXPINFO:
                                response_data = {'exp_ref': one.dict2ref(exp_ref), 'main_sync': True}
                                await communicator.info(net.base.ExpStatus.RUNNING, response_data, addr=addr)
                            case S.EXPSTATUS:
                                await communicator.status(net.base.ExpStatus.RUNNING, addr=addr)
                            case S.EXPINIT:
                                expected = one.dict2ref(exp_ref)
                                remote_ref = (data[0] or {}).get('exp_ref') if any(data) else None
                                if remote_ref and remote_ref != expected:
                                    log.critical('Experiment reference mismatch! Expected %s, got %s', expected, remote_ref)
                                data = {'exp_ref': one.dict2ref(exp_ref), 'status': net.base.ExpStatus.RUNNING}
                                await communicator.init(data, addr=addr)
                            case S.EXPSTART:
                                await communicator.start(exp_ref, addr=addr)
                            case S.ALYX:
                                base_url, token = data
                                if base_url and token and next(iter(token)):
                                    # Install alyx token
                                    update_alyx_token(data, addr, one.alyx)
                                elif one.alyx.is_logged_in and (base_url or one.alyx.base_url) == one.alyx.base_url:
                                    # Return alyx token
                                    await communicator.alyx(one.alyx, addr=addr)
                            case _:
                                # Do nothing for the others  # TODO Change iblrig mixin to not await on stop and cleanups
                                await communicator.confirmed_send((event, {'status': net.base.ExpStatus.RUNNING}), addr=addr)
                case _:
                    raise NotImplementedError(f'Unexpected task "{task.get_name()}"')
            tasks.remove(task)
