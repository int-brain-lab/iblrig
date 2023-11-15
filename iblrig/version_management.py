import re
import sys
from pathlib import Path
from subprocess import STDOUT, CalledProcessError, SubprocessError, check_call, check_output

import requests
from packaging import version

from iblrig import __version__
from iblrig.constants import BASE_DIR, IS_GIT
from iblrig.tools import ask_user, internet_available, static_vars
from iblutil.util import setup_logger

log = setup_logger('iblrig')


def check_for_updates() -> tuple[bool, str]:
    """
    Check for updates to the iblrig software.

    This function compares the locally installed version of iblrig with the
    latest available version to determine if an update is available.

    Returns:
        tuple[bool, Union[str, None]]: A tuple containing two elements.
            - A boolean indicating whether an update is available.
            - A string representing the latest available version, or None if
              no remote version information is available.
    """
    log.info('Checking for updates ...')

    update_available = False
    v_local = get_local_version()
    v_remote = get_remote_version()

    if v_local and v_remote:
        update_available = v_remote.base_version > v_local.base_version
        if update_available:
            log.info(f'Update to iblrig {v_remote.base_version} available')
        else:
            log.info('No update available')

    return update_available, v_remote.base_version if v_remote else ''


def get_local_version() -> version.Version | None:
    """
    Parse the local version string to obtain a Version object.

    This function attempts to parse the local version string (__version__)
    and returns a Version object representing the parsed version. If the
    parsing fails, it logs an error and returns None.

    Returns
    -------
    Union[version.Version, None]
        A Version object representing the parsed local version, or None if
        parsing fails.
    """
    try:
        log.debug('Parsing local version string')
        return version.parse(__version__)
    except (version.InvalidVersion, TypeError):
        log.error(f'Could not parse local version string: {__version__}')
        return None


def get_detailed_version_string(v_basic: str) -> str:
    """
    Generate a detailed version string based on a basic version string.

    This function takes a basic version string (major.minor.patch) and generates
    a detailed version string by querying Git for additional version information.
    The detailed version includes commit number of commits since the last tag,
    and Git status (dirty or broken). It is designed to fail safely.

    Parameters
    ----------
    v_basic : str
        A basic version string in the format 'major.minor.patch'.

    Returns
    -------
    str
        A detailed version string containing version information retrieved
        from Git, or the original basic version string if Git information
        cannot be obtained.

    Notes
    -----
    This method will only work with installations managed through Git.
    """

    if not internet_available():
        return v_basic

    if not IS_GIT:
        log.error('This installation of IBLRIG is not managed through git.')
        return v_basic

    # sanitize & check if input only consists of three fields - major, minor and patch - separated by dots
    v_sanitized = re.sub(r'^(\d+\.\d+\.\d+).*$$', r'\1', v_basic)
    if not re.match(r'^\d+\.\d+\.\d+$', v_sanitized):
        log.error(f"Couldn't parse version string: {v_basic}")
        return v_basic

    # get details through `git describe`
    try:
        get_remote_tags()
        v_detailed = check_output(
            ['git', 'describe', '--dirty', '--broken', '--match', v_sanitized, '--tags', '--long'],
            cwd=BASE_DIR,
            text=True,
            timeout=1,
            stderr=STDOUT,
        )
    except (SubprocessError, CalledProcessError) as e:
        log.debug(e, exc_info=True)
        return v_basic

    # apply a bit of regex magic for formatting & return the detailed version string
    v_detailed = re.sub(r'^((?:[\d+\.])+)(-[1-9]\d*)?(?:-0\d*)?(?:-\w+)(-dirty|-broken)?\n?$', r'\1\2\3', v_detailed)
    v_detailed = re.sub(r'-(\d+)', r'.post\1', v_detailed)
    v_detailed = re.sub(r'\-(dirty|broken)', r'+\1', v_detailed)
    return v_detailed


@static_vars(branch=None)
def get_branch() -> str | None:
    """
    Get the Git branch of the iblrig installation.

    This function retrieves and caches the Git branch of the iblrig installation.
    If the branch is already cached, it returns the cached value. If not, it
    attempts to obtain the branch from the Git repository.

    Returns
    -------
    Union[str, None]
        The Git branch of the iblrig installation, or None if it cannot be determined.

    Notes
    -----
    This method will only work with installations managed through Git.
    """
    if get_branch.branch is not None:
        return get_branch.branch
    if not IS_GIT:
        log.error('This installation of iblrig is not managed through git')
    try:
        get_branch.branch = check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=BASE_DIR, timeout=5, text=True
        ).removesuffix('\n')
        return get_branch.branch
    except (SubprocessError, CalledProcessError):
        return None


@static_vars(is_fetched_already=False)
def get_remote_tags() -> None:
    """
    Fetch remote Git tags if not already fetched.

    This function fetches remote Git tags if they have not been fetched already.
    If tags are already fetched, it does nothing. If the installation is not
    managed through Git, it logs an error.

    Returns
    -------
    None

    Notes
    -----
    This method will only work with installations managed through Git.
    """
    if get_remote_tags.is_fetched_already or not internet_available():
        return
    if not IS_GIT:
        log.error('This installation of iblrig is not managed through git')
    try:
        check_call(['git', 'fetch', 'origin', get_branch(), '-t', '-q', '-f'], cwd=BASE_DIR, timeout=5)
    except (SubprocessError, CalledProcessError):
        return
    get_remote_tags.is_fetched_already = True


@static_vars(changelog=None)
def get_changelog() -> str:
    """
    Retrieve the changelog for the iblrig installation.

    This function retrieves and caches the changelog for the iblrig installation
    based on the current Git branch. If the changelog is already cached, it
    returns the cached value. If not, it attempts to fetch the changelog from
    the GitHub repository or read it locally if the remote fetch fails.

    Returns
    -------
    str
        The changelog for the iblrig installation.

    Notes
    -----
    This method relies on the presence of a CHANGELOG.md file either in the
    repository or locally.
    """
    if get_changelog.changelog is not None:
        return get_changelog.changelog
    try:
        changelog = requests.get(
            f'https://raw.githubusercontent.com/int-brain-lab/iblrig/{get_branch()}/CHANGELOG.md', allow_redirects=True
        ).text
    except requests.RequestException:
        with open(Path(BASE_DIR).joinpath('CHANGELOG.md')) as f:
            changelog = f.read()
    get_changelog.changelog = changelog
    return get_changelog.changelog


@static_vars(remote_version=None)
def get_remote_version() -> version.Version | None:
    """
    Retrieve the remote version of iblrig from the Git repository.

    This function fetches and parses the remote version of the iblrig software
    from the Git repository. It uses Git tags to identify available versions.

    Returns
    -------
    Union[version.Version, None]
        A Version object representing the remote version if successfully obtained,
        or None if the remote version cannot be retrieved.

    Notes
    -----
    This method will only work with installations managed through Git.
    """
    if get_remote_version.remote_version is not None:
        log.debug(f'Using cached remote version: {get_remote_version.remote_version}')
        return get_remote_version.remote_version

    if not IS_GIT:
        log.error('Cannot obtain remote version: This installation of iblrig is not managed through git')
        return None

    if not internet_available():
        log.error('Cannot obtain remote version: Not connected to internet')
        return None

    try:
        log.debug('Obtaining remote version from github')
        get_remote_tags()
        references = check_output(
            ['git', 'ls-remote', '-t', '-q', '--exit-code', '--refs', 'origin', 'tags', '*'],
            cwd=BASE_DIR,
            timeout=5,
            encoding='UTF-8',
        )

    except (SubprocessError, CalledProcessError, FileNotFoundError):
        log.error('Could not obtain remote version string')
        return None

    try:
        log.debug('Parsing local version string')
        get_remote_version.remote_version = max([version.parse(v) for v in re.findall(r'/(\d+\.\d+\.\d+)', references)])
        return get_remote_version.remote_version
    except (version.InvalidVersion, TypeError):
        log.error('Could not parse remote version string')
        return None


def is_dirty() -> bool:
    """
    Check if the Git working directory is dirty (has uncommitted changes).

    Uses 'git diff --quiet' to determine if there are uncommitted changes in the Git repository.

    Returns:
        bool: True if the directory is dirty (has uncommitted changes) or an error occurs during execution,
              False if the directory is clean (no uncommitted changes).
    """
    try:
        return check_call(['git', 'diff', '--quiet'], cwd=BASE_DIR) != 0
    except CalledProcessError:
        return True


def upgrade() -> int:
    """
    Upgrade the IBLRIG software installation.

    This function upgrades the IBLRIG software installation to the latest version
    available in the Git repository. It checks the local and remote versions,
    confirms the upgrade with the user if necessary, and performs the upgrade.

    Returns
    -------
    int
        0 if the upgrade process is successfully completed.

    Raises
    ------
    Exception
        - If the installation is not managed through Git.
        - If the upgrade is attempted outside the IBLRIG virtual environment.
        - If the local version cannot be obtained.
        - If the remote version cannot be obtained.

    Notes
    -----
    This method requires that the installation is managed through Git and that
    the user is in the IBLRIG virtual environment.
    """
    if not internet_available():
        raise Exception('Connection to internet not available.')
    if not IS_GIT:
        raise Exception('This installation of IBLRIG is not managed through git.')
    if sys.base_prefix == sys.prefix:
        raise Exception('You need to be in the IBLRIG venv in order to upgrade.')

    try:
        v_local = get_local_version()
        assert v_local
    except AssertionError as e:
        raise Exception('Could not obtain local version.') from e

    try:
        v_remote = get_remote_version()
        assert v_remote
    except AssertionError as e:
        raise Exception('Could not obtain remote version.') from e

    print(f'Local version:  {v_local}')
    print(f'Remote version: {v_remote}\n')

    if v_local >= v_remote and not ask_user('No need to upgrade. Do you want to run the upgrade routine anyways?', False):
        return 0

    if is_dirty():
        print('There are changes in your local copy of IBLRIG that will be lost when upgrading.')
        if not ask_user('Do you want to proceed?', False):
            return 0
        check_call(['git', 'reset', '--hard'], cwd=BASE_DIR)

    check_call(['git', 'pull', '--tags'], cwd=BASE_DIR)
    check_call([sys.executable, '-m', 'pip', 'install', '-U', 'pip'], cwd=BASE_DIR)
    check_call([sys.executable, '-m', 'pip', 'install', '-U', '-e', BASE_DIR], cwd=BASE_DIR)
    return 0
