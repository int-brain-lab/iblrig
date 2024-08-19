"""
Purge data from RIG.

- looks for datasets matching filename pattern
- datasets that exist in ONE cache are removed
"""

import argparse
import logging
from fnmatch import fnmatch
from pathlib import Path

from one.alf.files import get_session_path
from one.alf.io import iter_datasets, iter_sessions
from one.api import ONE

log = logging.getLogger('iblrig')


def session_name(path: str | Path, lab: str | None = None) -> str:
    """
    Return the session name (`subject/date/number`) string for a given session path.

    If lab is given return `lab/Subjects/subject/date/number`.

    Parameters
    ----------
    path : str or Path
        Session path.
    lab : str, optional
        Lab name
    """
    lab = f'{lab}/Subjects/' if lab else ''
    return lab + '/'.join(get_session_path(path).parts[-3:])


def local_alf_paths(root_dir: str | Path, filename: str):
    """
    Yield session path and relative paths of ALFs that match filename pattern.

    Parameters
    ----------
    root_dir : str or Path
        The folder to look for sessions.
    filename : str
        Session filename.

    Yields
    ------
    session_path : Path
        Session path.
    dataset : Path
        Relative paths of ALFs.
    """
    for session_path in iter_sessions(root_dir):
        for dataset in iter_datasets(session_path):
            if fnmatch(dataset, filename):
                yield session_path, dataset


def purge_local_data(local_folder, filename='*', lab=None, dry=False, one=None):
    # Figure out datasetType from filename or file path
    local_folder = Path(local_folder)

    # Get matching files that exist in ONE cache
    to_remove = []
    one = one or ONE()
    for session_path, dataset in local_alf_paths(local_folder, filename):
        session = session_name(session_path, lab=lab)
        eid = one.to_eid(session)
        if not eid:
            continue
        matching = one.list_datasets(eid, dataset.as_posix())
        if not matching:
            continue
        assert len(matching) == 1
        to_remove.append(local_folder.joinpath(session_path, dataset))

    log.info(f'Local files to remove: {len(to_remove)}')
    for f in to_remove:
        log.info(f'DELETE: {f}')
        f.unlink() if not dry else None
    return to_remove


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Delete files from rig')
    parser.add_argument('folder', help='Local iblrig_data folder')
    parser.add_argument('file', help='File name to search and destroy for every session')
    parser.add_argument(
        '-lab', required=False, default=None, help='Lab name, in case sessions conflict between labs. default: None'
    )
    parser.add_argument('--dry', required=False, default=False, action='store_true', help='Dry run? default: False')
    args = parser.parse_args()
    purge_local_data(args.folder, args.file, lab=args.lab, dry=args.dry)
    print('purge_rig_data script done\n')
