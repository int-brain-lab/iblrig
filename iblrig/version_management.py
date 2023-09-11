from packaging import version
from pathlib import Path
from re import sub
from subprocess import check_output, check_call, SubprocessError

import iblrig
from iblutil.util import setup_logger

log = setup_logger('iblrig')

def check_for_updates():
    log.info('Checking for updates ...')

    # assert that git is being used
    dir_base = Path(iblrig.__file__).parents[1]
    if not dir_base.joinpath('.git').exists():
        log.debug('iblrig does not seem to be managed through git')
        return -1, ''

    # get newest remote tag
    try:
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=dir_base)
        branch = sub(r'\n', '', branch.decode())
        check_call(["git", "fetch", "origin", branch, "-q"], cwd=dir_base, timeout=5)
        version_remote_str = check_output(["git", "describe", "--tags", "--abbrev=0"],
                                          cwd=dir_base)
        version_remote_str = sub(r'[^\d\.]', '', version_remote_str.decode())
    except (SubprocessError, FileNotFoundError):
        log.debug(f'Could not fetch remote tags')
        return -1, ''

    # parse version information
    try:
        version_local = version.parse(iblrig.__version__)
        version_remote = version.parse(version_remote_str)
    except version.InvalidVersion:
        log.debug(f'Invalid version string')
        return -1, ''

    if version_remote > version_local:
        log.info(f'Update to iblrig {version_remote_str} found.')
    else:
        log.info(f'No update found.')
    return version_remote > version_local, version_remote_str
