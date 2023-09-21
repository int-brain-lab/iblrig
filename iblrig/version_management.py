from packaging import version
from re import findall
from subprocess import check_output, check_call, SubprocessError
import sys

from iblrig import __version__ as VERSION_LOCAL
from iblrig.constants import BASE_DIR, IS_GIT
from iblutil.util import setup_logger

log = setup_logger('iblrig')

_remote_version = None


def check_for_updates():
    log.info('Checking for updates ...')

    v_remote = get_remote_version()
    if v_remote is None:
        return -1, ''

    if v_remote > VERSION_LOCAL:
        log.info(f'Update to iblrig {v_remote} found.')
    else:
        log.info('No update found.')
    return v_remote > VERSION_LOCAL, str(v_remote)


def get_local_version():
    try:
        log.debug('Parsing local version string')
        return version.parse(VERSION_LOCAL)
    except (version.InvalidVersion, TypeError):
        log.error(f'Could not parse local version string: {VERSION_LOCAL}')
        return None


def get_remote_version():
    global _remote_version

    if _remote_version:
        return _remote_version

    if not IS_GIT:
        return None

    try:
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=BASE_DIR, timeout=5, encoding='UTF-8').removesuffix('\n')
        check_call(["git", "fetch", "origin", branch, "-t", "-q"], cwd=BASE_DIR, timeout=5)
        references = check_output(["git", "ls-remote", "-t", "-q", "--exit-code", "--refs", "origin", "tags", "*"],
                                  cwd=BASE_DIR, timeout=5, encoding='UTF-8')
    except (SubprocessError, FileNotFoundError):
        log.error('Could not obtain remote version string')
        return None
    try:
        _remote_version = max([version.parse(v) for v in findall(r'/([\d.]+)', references)])
        return _remote_version
    except (version.InvalidVersion, TypeError):
        log.error('Could not parse remote version string')
        return None


def upgrade():
    if not IS_GIT:
        raise Exception('This installation of IBLRIG is not managed through git.')
    if sys.base_prefix == sys.prefix:
        raise Exception('You need to be in the IBLRIG venv in order to upgrade.')

    v_local = get_local_version()
    v_remote = get_remote_version()

    if not v_local:
        raise Exception('Could not obtain local version.')
    if not v_remote:
        raise Exception('Could not obtain remote version.')

    print(f'Local version:  {v_local}')
    print(f'Remote version: {v_remote}')

    if v_local >= v_remote:
        print('No need to upgrade.')
        return 0

    if VERSION_LOCAL.endswith('+dirty'):
        print('There are changes in your local copy of IBLRIG that will be lost when '
              'upgrading.')
        while True:
            user_input = input('Do you want to proceed? [y, N] ')
            if user_input.lower() in ['n', 'no', '']:
                return
            if user_input.lower() in ['y', 'yes']:
                check_call([sys.executable, "-m", "pip", "reset", "--hard"])
                break

    check_call([sys.executable, "git", "pull"])
    check_call([sys.executable, "-m", "pip", "install", "-U", "-e", "."])
