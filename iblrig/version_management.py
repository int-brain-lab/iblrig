from typing import Union

from packaging import version
from re import findall
from subprocess import check_output, check_call, SubprocessError
import sys

from iblrig import __version__
from iblrig.constants import BASE_DIR, IS_GIT
from iblutil.util import setup_logger

log = setup_logger('iblrig')

_remote_version: version.Version = None


def check_for_updates() -> tuple[bool, Union[str, None]]:
    log.info('Checking for updates ...')

    update_available = False
    v_local = get_local_version()
    v_remote = get_remote_version()

    if all((v_remote, v_local)):
        v_remote_base = version.parse(v_remote.base_version)
        v_local_base = version.parse(v_local.base_version)

        if v_remote_base > v_local_base:
            log.info(f'Update to iblrig {v_remote.base_version} available.')
        else:
            log.info('No update available.')
        update_available = v_remote > v_local

    return update_available, v_remote.base_version if v_remote else ''


def get_local_version() -> Union[version.Version, None]:
    try:
        log.debug('Parsing local version string')
        return version.parse(__version__)
    except (version.InvalidVersion, TypeError):
        log.error(f'Could not parse local version string: {__version__}')
        return None


def get_remote_version() -> Union[version.Version, None]:
    global _remote_version

    if _remote_version:
        log.debug(f'Using cached remote version: {_remote_version}')
        return _remote_version

    if not IS_GIT:
        log.error('This installation of iblrig is not managed through git - cannot obtain remote version')
        return None

    try:
        log.debug('Obtaining remote version from github')
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=BASE_DIR, timeout=5, encoding='UTF-8').removesuffix('\n')
        check_call(["git", "fetch", "origin", branch, "-t", "-q"], cwd=BASE_DIR, timeout=5)
        references = check_output(["git", "ls-remote", "-t", "-q", "--exit-code", "--refs", "origin", "tags", "*"],
                                  cwd=BASE_DIR, timeout=5, encoding='UTF-8')
    except (SubprocessError, FileNotFoundError):
        log.error('Could not obtain remote version string')
        return None
    try:
        log.debug('Parsing local version string')
        _remote_version = max([version.parse(v) for v in findall(r'/(\d+\.\d+\.\d+)', references)])
        return _remote_version
    except (version.InvalidVersion, TypeError):
        log.error('Could not parse remote version string')
        return None


def upgrade() -> int:
    if not IS_GIT:
        raise Exception('This installation of IBLRIG is not managed through git.')
    if sys.base_prefix == sys.prefix:
        raise Exception('You need to be in the IBLRIG venv in order to upgrade.')

    try:
        v_local = get_local_version()
        assert v_local
    except AssertionError:
        raise Exception('Could not obtain local version.')

    try:
        v_remote = get_remote_version()
        assert v_remote
    except AssertionError:
        raise Exception('Could not obtain remote version.')

    print(f'Local version:  {v_local}')
    print(f'Remote version: {v_remote}\n')

    if v_local >= v_remote:
        if not _ask_user('No need to upgrade. Do you want to run the upgrade routine anyways?', False):
            return 0

    if v_local.local == 'dirty':
        print('There are changes in your local copy of IBLRIG that will be lost when upgrading.')
        if not _ask_user('Do you want to proceed?', False):
            return 0
        check_call([sys.executable, "-m", "pip", "reset", "--hard"])

    check_call([sys.executable, "git", "pull"])
    check_call([sys.executable, "-m", "pip", "install", "-U", "-e", "."])


def _ask_user(prompt: str, default: bool = False) -> bool:
    prompt = f'{prompt} [Y, n] ' if default is True else f'{prompt} [y, N] '
    inputs_no = ['n', 'no'] if default is True else ['n', 'no', '']
    inputs_yes = ['y', 'yes', ''] if default is True else ['y', 'yes']

    while True:
        user_input = input(prompt)
        if user_input.lower() in inputs_no:
            return False
        if user_input.lower() in inputs_yes:
            return True
