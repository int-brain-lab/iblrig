# WARNING: CHANGES TO THIS FILE WILL DIRECTLY IMPACT THE USER'S ABILITY TO
# AUTOMATICALLY UPGRADE THE SYSTEM. MODIFY WITH EXTREME CAUTION AND ONLY IF
# ABSOLUTELY NECESSARY.
import sys
from subprocess import CalledProcessError, SubprocessError, run

import colorlog

from iblrig.constants import BASE_DIR
from iblrig.tools import ask_user
from iblrig.version_management import check_upgrade_prerequisites, get_local_version, get_remote_version, is_dirty

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(message)s'))

log = colorlog.getLogger(__name__)
log.setLevel(colorlog.INFO)
log.addHandler(handler)


def _exit_or_raise(message: str | Exception, raise_exception: bool = True, return_code: int | None = None):
    """
    Handle errors by either raising an exception or logging an error message and
    exiting the program.

    Parameters
    ----------
    message : str or Exception
        The error message or an Exception to be handled.
    raise_exception : bool, optional
        If True, raise the provided Exception or a new Exception with the
        provided error message. If False, log the error message and exit the
        program. Defaults to True.
    return_code : int or None, optional
        The exit code to be used with sys.exit() if raise_exception is False.
        If None, attempt to extract the return code from the provided Exception
        (if it's a CalledProcessError), defaulting to 1 if no return code is
        found.

    Raises
    ------
    Exception
        If raise_exception is True, raise the provided Exception or a new
        Exception with the provided error message.

    Exits
    -----
    sys.exit(return_code)
        If raise_exception is False, log the error message, and exit the program
        with the specified return code.
    """
    if raise_exception:
        raise message if isinstance(message, Exception) else Exception(message)
    else:
        if return_code is None:
            return_code = message.returncode if isinstance(message, CalledProcessError) else 1
        if isinstance(message, Exception):
            message = str(message)
        log.error(f'{message}')
        sys.exit(return_code)


def call_subprocesses(reset_repo: bool = False, **kwargs) -> None:
    """
    Perform upgrade-related subprocess calls.

    Parameters
    ----------
    reset_repo : bool, optional
        If True, reset the local Git repository to its remote state before
        upgrading.
    **kwargs
        Additional keyword arguments to be passed to subprocess calls.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    subprocess.CalledProcessError
        If any subprocess calls result in a non-zero return code.
    FileNotFoundError
        If any of the subprocess commands executable is not found.
    """
    calls = [
        ['git', 'pull', '--tags'],
        [sys.executable, '-m', 'pip', 'install', '-U', 'pip'],
        [sys.executable, '-m', 'pip', 'install', '-U', '-e', BASE_DIR],
    ]
    if reset_repo:
        calls.insert(0, ['git', 'reset', '--hard'])
    for call in calls:
        log.warning('\n' + ' '.join(call))
        run(call, cwd=BASE_DIR, check=True, **kwargs)


def upgrade(raise_exceptions: bool = False, allow_reset: bool = False):
    """
    Upgrade the IBLRIG software installation.

    This function upgrades the IBLRIG software installation to the latest
    version available in the Git repository. It checks the local and remote
    versions, confirms the upgrade with the user if necessary, and performs the
    upgrade.
    """
    # check some basics
    check_upgrade_prerequisites(exception_handler=_exit_or_raise, raise_exception=raise_exceptions)

    # get local and remote version
    if (v_local := get_local_version()) is None:
        _exit_or_raise('Could not obtain local version of IBLRIG.', raise_exception=raise_exceptions)
    if (v_remote := get_remote_version()) is None:
        _exit_or_raise('Could not obtain remote version of IBLRIG.', raise_exception=raise_exceptions)
    print(f'Local version:  {v_local}')
    print(f'Remote version: {v_remote}')
    if v_local >= v_remote and not ask_user('\nNo need to upgrade. Do you want to run the upgrade routine anyways?', False):
        sys.exit(0)

    # check dirty state
    if reset_repo := is_dirty():
        print('\nThere are local changes in your copy of IBLRIG that will be lost when upgrading.')
        if not ask_user('Do you want to proceed?', False):
            sys.exit(0)

    # call subprocesses and report outcome
    try:
        call_subprocesses(reset_repo=reset_repo)
    except (FileNotFoundError, SubprocessError, Exception) as e:
        if raise_exceptions:
            raise e
        else:
            log.exception(e)
            log.error(
                f'\nAutomatic Upgrade of IBLRIG was NOT successful.\n'
                f'Please run the following commands for a manual upgrade:\n\n'
                f'    git pull --tags {BASE_DIR}\n'
                f'    pip install -U -e {BASE_DIR}\n'
            )
            sys.exit(e.returncode if isinstance(e, CalledProcessError) else 1)
    else:
        log.info(f'\nUpgrade to IBLRIG {v_remote} was successful.\n')
        sys.exit(0)
