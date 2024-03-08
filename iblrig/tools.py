import logging
import os
import re
import shutil
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from iblrig.constants import BONSAI_EXE
from iblrig.path_helper import create_bonsai_layout_from_template, load_pydantic_yaml
from iblrig.pydantic_definitions import RigSettings

log = logging.getLogger(__name__)


def ask_user(prompt: str, default: bool = False) -> bool:
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


def get_anydesk_id(silent: bool = False) -> str | None:
    """
    Retrieve the AnyDesk ID of the current machine.

    Parameters
    ----------
    silent : bool, optional
        If True, suppresses exceptions and logs them instead.
        If False (default), raises exceptions.

    Returns
    -------
    str or None
        The AnyDesk ID as a formatted string (e.g., '123 456 789') if successful,
        or None on failure.

    Raises
    ------
    FileNotFoundError
        If the AnyDesk executable is not found.
    subprocess.CalledProcessError
        If an error occurs while executing the AnyDesk command.
    StopIteration
        If the subprocess output is empty.
    UnicodeDecodeError
        If there is an issue decoding the subprocess output.

    Notes
    -----
    The function attempts to find the AnyDesk executable and retrieve the ID using the command line.
    On success, the AnyDesk ID is returned as a formatted string. If silent is True, exceptions are logged,
    and None is returned on failure. If silent is False, exceptions are raised on failure.
    """
    anydesk_id = None
    try:
        if cmd := shutil.which('anydesk'):
            pass
        elif os.name == 'nt':
            cmd = str(Path(os.environ['PROGRAMFILES(X86)'], 'AnyDesk', 'anydesk.exe'))
        if cmd is None or not Path(cmd).exists():
            raise FileNotFoundError('AnyDesk executable not found')

        proc = subprocess.Popen([cmd, '--get-id'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.stdout and re.match(r'^\d{10}$', id_string := next(proc.stdout).decode()):
            anydesk_id = f'{int(id_string):,}'.replace(',', ' ')
    except (FileNotFoundError, subprocess.CalledProcessError, StopIteration, UnicodeDecodeError) as e:
        if silent:
            log.debug(e, exc_info=True)
        else:
            raise e
    return anydesk_id


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


@static_vars(return_value=None)
def internet_available(host: str = '8.8.8.8', port: int = 53, timeout: int = 3, force_update: bool = False) -> bool:
    """
    Check if the internet connection is available.

    This function checks if an internet connection is available by attempting to
    establish a connection to a specified host and port. It will use a cached
    result if the latter is available and `force_update` is set to False.

    Parameters
    ----------
    host : str, optional
        The IP address or domain name of the host to check the connection to.
        Default is "8.8.8.8" (Google's DNS server).
    port : int, optional
        The port to use for the connection check. Default is 53 (DNS port).
    timeout : int, optional
        The maximum time (in seconds) to wait for the connection attempt.
        Default is 3 seconds.
    force_update : bool, optional
        If True, force an update and recheck the internet connection even if
        the result is cached. Default is False.

    Returns
    -------
    bool
        True if an internet connection is available, False otherwise.
    """
    if not force_update and internet_available.return_value:
        return internet_available.return_value
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        internet_available.return_value = True
    except OSError:
        internet_available.return_value = False
    return internet_available.return_value


def alyx_reachable() -> bool:
    """
    Check if Alyx can be connected to.

    Returns
    -------
    bool
        True if Alyx can be connected to, False otherwise.
    """
    settings: RigSettings = load_pydantic_yaml(RigSettings)
    if settings.ALYX_URL is not None:
        return internet_available(host=settings.ALYX_URL.host, port=443, timeout=1, force_update=True)
    return False


def call_bonsai(
    workflow_file: str | Path,
    parameters: dict[str, Any] | None = None,
    start: bool = True,
    debug: bool = False,
    bootstrap: bool = True,
    editor: bool = True,
    wait: bool = True,
    check: bool = False,
) -> subprocess.Popen[bytes] | subprocess.Popen[str | bytes | Any] | subprocess.CompletedProcess:
    """
    Execute a Bonsai workflow within a subprocess call.

    Parameters
    ----------
    workflow_file : str | Path
        Path to the Bonsai workflow file.
    parameters : dict[str, str], optional
        Parameters to be passed to Bonsai workflow.
    start : bool, optional
        Start execution of the workflow within Bonsai (default is True)
    debug : bool, optional
        Enable debugging mode if True (default is False).
        Only applies if editor is True.
    bootstrap : bool, optional
        Enable Bonsai bootstrapping if True (default is True).
    editor : bool, optional
        Enable Bonsai editor if True (default is True).
    wait : bool, optional
        Wait for Bonsai process to finish (default is True).
    check : bool, optional
        Raise CalledProcessError if Bonsai process exits with non-zero exit code (default is False).
        Only applies if wait is True.

    Returns
    -------
    Popen[bytes] | Popen[str | bytes | Any] | CompletedProcess
        Pointer to the Bonsai subprocess if wait is False, otherwise subprocess.CompletedProcess.

    Raises
    ------
    FileNotFoundError
        If the Bonsai executable does not exist.
        If the specified workflow file does not exist.

    """
    if not BONSAI_EXE.exists():
        FileNotFoundError(BONSAI_EXE)
    workflow_file = Path(workflow_file)
    if not workflow_file.exists():
        raise FileNotFoundError(workflow_file)
    cwd = workflow_file.parent
    create_bonsai_layout_from_template(workflow_file)

    cmd = [str(BONSAI_EXE), str(workflow_file)]
    if start:
        cmd.append('--start' if debug else '--start-no-debug')
    if not editor:
        cmd.append('--no-editor')
    if not bootstrap:
        cmd.append('--no-boot')
    if parameters is not None:
        for key, value in parameters.items():
            cmd.append(f'-p:{key}={str(value)}')

    log.info(f'Starting Bonsai workflow `{workflow_file.name}`')
    log.debug(' '.join(str(cmd)))
    if wait:
        return subprocess.run(args=cmd, cwd=cwd, check=check)
    else:
        return subprocess.Popen(args=cmd, cwd=cwd)
