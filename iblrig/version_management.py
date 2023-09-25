from typing import Union, Callable, Any

from packaging import version
import re
from subprocess import check_output, check_call, SubprocessError, CalledProcessError, STDOUT
import sys

from iblrig import __version__
from iblrig.constants import BASE_DIR, IS_GIT
from iblutil.util import setup_logger

log = setup_logger('iblrig')


def static_vars(**kwargs) -> Callable[..., Any]:
    """
    Decorator to add static variables to a function.

    This decorator allows you to add static variables to a function by providing
    keyword arguments. Static variables are shared across all calls to the
    decorated function.

    Parameters
    ----------
    **kwargs
        Keyword arguments where the keys are variable names and the values are
        the initial values of the static variables.

    Returns
    -------
    function
        A decorated function with the specified static variables.
    """
    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate


def check_for_updates() -> tuple[bool, Union[str, None]]:
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

    # this method will only work with installations managed through git
    if not IS_GIT:
        log.error('This installation of IBLRIG is not managed through git.')
        return v_basic

    # sanitize & check if input only consists of three fields - major, minor and patch - separated by dots
    v_sanitized = re.sub(r'^(\d+\.\d+\.\d+).*$$', r'\1', v_basic)
    if not re.match(r'^\d+\.\d+\.\d+$', v_sanitized):
        log.error(f'Couldn\'t parse version string: {v_basic}')
        return v_basic

    # get details through `git describe`
    try:
        fetch_remote_tags()
        v_detailed = check_output(["git", "describe", "--dirty", "--broken", "--match", v_sanitized, "--tags", "--long"],
                                  cwd=BASE_DIR, text=True, timeout=1, stderr=STDOUT)
    except (SubprocessError, CalledProcessError):
        log.error('Error calling `git describe`')
        return v_basic

    # apply a bit of regex magic for formatting & return the detailed version string
    v_detailed = re.sub(r'^((?:[\d+\.])+)(-\d+)?(-\w+)(-dirty|-broken)?\n$', r'\1\2\4', v_detailed)
    v_detailed = re.sub(r'-(\d+)', r'-post\1', v_detailed)
    v_detailed = re.sub(r'\-(dirty|broken)', r'.\1', v_detailed)
    return v_detailed


@static_vars(is_fetched_already=False)
def fetch_remote_tags() -> None:
    if fetch_remote_tags.is_fetched_already:
        return
    if not IS_GIT:
        log.error('This installation of iblrig is not managed through git')
    try:
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=BASE_DIR, timeout=5, text=True).removesuffix('\n')
        check_call(["git", "fetch", "origin", branch, "-t", "-q"], cwd=BASE_DIR, timeout=5)
    except (SubprocessError, CalledProcessError):
        return
    fetch_remote_tags.is_fetched_already = True


@static_vars(remote_version=None)
def get_remote_version() -> Union[version.Version, None]:
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
    if get_remote_version.remote_version:
        log.debug(f'Using cached remote version: {get_remote_version.remote_version}')
        return get_remote_version.remote_version

    if not IS_GIT:
        log.error('This installation of iblrig is not managed through git - cannot obtain remote version')
        return None

    try:
        log.debug('Obtaining remote version from github')
        fetch_remote_tags()
        references = check_output(["git", "ls-remote", "-t", "-q", "--exit-code", "--refs", "origin", "tags", "*"],
                                  cwd=BASE_DIR, timeout=5, encoding='UTF-8')

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

    # check_call([sys.executable, "git", "pull", "--tags"])
    # check_call([sys.executable, "-m", "pip", "install", "-U", "-e", "."])


def _ask_user(prompt: str, default: bool = False) -> bool:
    """
    Prompt the user for a yes/no response.

    This function displays a prompt to the user and expects a yes or no response.
    The response is not case-sensitive. If the user presses Enter without
    typing anything, the function interprets it as the default response.

    Parameters
    ----------
    prompt : str
        The prompt message to display to the user.
    default : bool, optional
        The default response when the user presses Enter without typing
        anything. If True, the default response is 'yes' (Y/y or Enter).
        If False, the default response is 'no' (N/n or Enter).

    Returns
    -------
    bool
        True if the user responds with 'yes'
        False if the user responds with 'no'
    """
    while True:
        user_input = input(f'{prompt} [Y/n] ' if default else f'{prompt} [y/N] ').strip().lower()
        if not user_input:
            return default
        elif user_input in ['y', 'yes']:
            return True
        elif user_input in ['n', 'no']:
            return False
