import logging
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from subprocess import STDOUT, CalledProcessError, SubprocessError, check_call, check_output
from typing import Any, Literal

import requests
from packaging import version

from iblrig import __version__
from iblrig.constants import BASE_DIR, IS_GIT, IS_VENV
from iblrig.tools import internet_available, static_vars

log = logging.getLogger(__name__)


def check_for_updates() -> tuple[bool, str]:
    """
    Check for updates to the iblrig software.

    This function compares the locally installed version of iblrig with the
    latest available version to determine if an update is available.

    Returns
    -------
        tuple[bool, Union[str, None]]: A tuple containing two elements.
            - A boolean indicating whether an update is available.
            - A string representing the latest available version, or None if
              no remote version information is available.
    """
    log.debug('Checking for updates ...')

    update_available = False
    v_local = get_local_version()
    v_remote = get_remote_version()

    if v_local and v_remote:
        update_available = v_remote.base_version > v_local.base_version
        if update_available:
            log.info(f'Update to iblrig {v_remote.base_version} available')
        else:
            log.debug('No update available')

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


cached_check_output = cache(check_output)
OnErrorLiteral = Literal['raise', 'log', 'silence']


def call_git(*args: str, cache_output: bool = True, on_error: OnErrorLiteral = 'raise') -> str | None:
    """
    Call a git command with the specified arguments.

    This function executes a git command with the provided arguments. It can cache the output of the command
    and handle errors based on the specified behavior.

    Parameters
    ----------
    *args : str
        The arguments to pass to the git command.
    cache_output : bool, optional
        Whether to cache the output of the command. Default is True.
    on_error : str, optional
        The behavior when an error occurs. Either
        - 'raise': raise the exception (default),
        - 'log': log the exception, or
        - 'silence': suppress the exception.

    Returns
    -------
    str or None
        The output of the git command as a string, or None if an error occurred.

    Raises
    ------
    RuntimeError
        If the installation is not managed through git and on_error is set to 'raise'.
    SubprocessError
        If the command fails and on_error is set to 'raise'.
    """
    kwargs: dict[str, Any] = {'args': ('git', *args), 'cwd': BASE_DIR, 'timeout': 5, 'text': True}
    if not IS_GIT:
        message = 'This installation of iblrig is not managed through git'
        if on_error == 'raise':
            raise RuntimeError(message)
        elif on_error == 'log':
            log.error(message)
        return None
    try:
        output = cached_check_output(**kwargs) if cache_output else check_output(**kwargs)
        return output.strip()
    except SubprocessError as e:
        if on_error == 'raise':
            raise e
        elif on_error == 'log':
            log.exception(e)
        return None


def get_branch() -> str | None:
    """
    Get the Git branch of the iblrig installation.

    Returns
    -------
    str or None
        The Git branch of the iblrig installation, or None if it cannot be determined.
    """
    return call_git('rev-parse', '--abbrev-ref', 'HEAD', on_error='log')


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
    if (branch := get_branch()) is None:
        return
    try:
        check_call(['git', 'fetch', 'origin', branch, '-t', '-q', '-f'], cwd=BASE_DIR, timeout=5)
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

    Returns
    -------
        bool: True if the directory is dirty (has uncommitted changes) or an error occurs during execution,
              False if the directory is clean (no uncommitted changes).
    """
    try:
        return check_call(['git', 'diff', '--quiet'], cwd=BASE_DIR) != 0
    except CalledProcessError:
        return True


def check_upgrade_prerequisites(exception_handler: Callable | None = None, *args, **kwargs) -> None:
    """Check prerequisites for upgrading IBLRIG.

    This function verifies the prerequisites necessary for upgrading IBLRIG. It checks for
    internet connectivity, whether the IBLRIG installation is managed through Git, and
    whether the script is running within the IBLRIG virtual environment.

    Parameters
    ----------
    exception_handler : Callable, optional
        An optional callable that handles exceptions if raised during the check.
        If provided, it will be called with the exception as the first argument,
        followed by any additional positional arguments (*args), and any
        additional keyword arguments (**kwargs).

    *args : Additional positional arguments
        Any additional positional arguments needed by the `exception_handler` callable.

    **kwargs : Additional keyword arguments
        Any additional keyword arguments needed by the `exception_handler` callable.


    Raises
    ------
    ConnectionError
        If there is no connection to the internet.
    RuntimeError
        If the IBLRIG installation is not managed through Git, or
        if the script is not running within the IBLRIG virtual environment.
    """
    try:
        if not internet_available():
            raise ConnectionError('No connection to internet.')
        if not IS_GIT:
            raise RuntimeError('This installation of IBLRIG is not managed through Git.')
        if not IS_VENV:
            raise RuntimeError('You need to be in the IBLRIG virtual environment in order to upgrade.')
    except (ConnectionError, RuntimeError) as e:
        if callable(exception_handler):
            exception_handler(e, *args, **kwargs)
        else:
            raise e
