"""
Purge data from RIG
- looks for datasets matching filename pattern
- datasets that exist in ONE cache are removed
"""
import argparse
import logging
from fnmatch import fnmatch
from pathlib import Path

import one
from one.alf.files import get_session_path
from one.api import ONE

log = logging.getLogger('iblrig')

try:  # Verify ONE-api is at v1.13.0 or greater
    assert(tuple(map(int, one.__version__.split('.'))) >= (1, 13, 0))
    from one.alf.cache import iter_datasets, iter_sessions
except (AssertionError, ImportError) as e:
    if e is AssertionError:
        log.error("The found version of ONE needs to be updated to run this script, please run a 'pip install -U ONE-api' from "
                  "the appropriate anaconda environment")
    raise


def session_name(path, lab=None) -> str:
    """
    Returns the session name (subject/date/number) string for a given session path. If lab is given
    returns lab/Subjects/subject/date/number.
    """
    lab = f'{lab}/Subjects/' if lab else ''
    return lab + '/'.join(get_session_path(path).parts[-3:])


def local_alf_paths(root_dir, filename):
    """Yield session path and relative paths of ALFs that match filename pattern"""
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
        if not dry:
            f.unlink()
    return to_remove


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Delete files from rig')
    parser.add_argument('folder', help='Local iblrig_data folder')
    parser.add_argument('file', help='File name to search and destroy for every session')
    parser.add_argument(
        '-lab', required=False, default=None, help='Lab name, in case sessions conflict between labs. default: None',
    )
    parser.add_argument(
        '--dry', required=False, default=False, action='store_true', help='Dry run? default: False',
    )
    args = parser.parse_args()
    purge_local_data(args.folder, args.file, lab=args.lab, dry=args.dry)
    print('Done\n')
