from packaging import version
from pathlib import Path
from re import sub
from subprocess import check_output, check_call, SubprocessError
import sys

import iblrig
from iblutil.util import setup_logger

log = setup_logger('iblrig')


def check_for_updates():
    log.info('Checking for updates ...')

    try:
        v_local = version.parse(iblrig.__version__)
    except (version.InvalidVersion, TypeError):
        log.debug('Could not parse local version string')
        return -1, ''

    v_remote = Remote().version()
    if v_remote is None:
        log.debug('Could not parse remote version string')
        return -1, ''

    if v_remote > v_local:
        log.info(f'Update to iblrig {v_remote} found.')
    else:
        log.info('No update found.')
    return (v_remote > v_local, str(v_remote) if v_remote > v_local else str(v_local))


def update_available():
    version_local = version.parse(iblrig.__version__)
    version_remote = version.parse(Remote().version_str())
    return version_remote > version_local


class Remote(object):
    _version = None

    @staticmethod
    def version():

        if Remote._version:
            return Remote._version

        if not is_git():
            return None
        try:
            dir_base = Path(iblrig.__file__).parents[1]
            branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                  cwd=dir_base)
            branch = sub(r'\n', '', branch.decode())
            check_call(["git", "fetch", "origin", branch, "-q"],
                       cwd=dir_base, timeout=5)
            version_str = check_output(["git", "describe", "--tags", "--abbrev=0"],
                                       cwd=dir_base)
        except (SubprocessError, FileNotFoundError):
            return None

        version_str = sub(r'[^\d\.]', '', version_str.decode())
        try:
            Remote._version = version.parse(version_str)
            return Remote._version
        except (version.InvalidVersion, TypeError):
            return None


def is_git():
    return Path(iblrig.__file__).parents[1].joinpath('.git').exists()


def upgrade():
    if not is_git():
        raise Exception('This installation of IBLRIG is not managed through git.')
    if sys.base_prefix == sys.prefix:
        raise Exception('You need to be in the IBLRIG venv in order to upgrade.')
    if not Remote.version():
        raise Exception('Could not obtain remote version.')

    local_version = version.parse(iblrig.__version__)
    remote_version = Remote.version()

    print(f'Local version:  {local_version}')
    print(f'Remote version: {remote_version}')

    if local_version >= remote_version:
        print('No need to upgrade.')
        return 0

    if iblrig.__version__.endswith('+dirty'):
        print('There are changes in your local copy of IBLRIG that will be lost when '
              'upgrading.')
        while True:
            user_input = input('Do you want to proceed? [y, N] ')
            if user_input.lower() in ['n', 'no', '']:
                return
            if user_input.lower() in ['y', 'yes']:
                break

    check_call([sys.executable, "-m", "pip", "install", "-U", "-e", "."])
