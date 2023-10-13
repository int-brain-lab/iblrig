import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Callable, Any, Optional

from iblutil.util import setup_logger

logger = setup_logger("iblrig")


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


def get_anydesk_id(silent: bool = False) -> Optional[str]:
    anydesk_id = None
    try:
        if cmd := shutil.which('anydesk'):
            cmd = Path(cmd)
        elif os.name == 'nt':
            cmd = Path(os.environ["ProgramFiles(x86)"], 'AnyDesk', 'anydesk.exe')
        if not cmd.exists():
            raise FileNotFoundError("AnyDesk executable not found")

        proc = subprocess.Popen([cmd, '--get-id'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.stdout and re.match(r'^\d{10}$', id_string := next(proc.stdout).decode()):
            anydesk_id = '{:,}'.format(int(id_string)).replace(',', ' ')
    except (FileNotFoundError, subprocess.CalledProcessError, StopIteration, UnicodeDecodeError) as e:
        if silent:
            logger.debug(e, exc_info=True)
        else:
            raise e
    finally:
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
def internet_available(host: str = "8.8.8.8", port: int = 53, timeout: int = 3, force_update: bool = False):
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
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        internet_available.return_value = True
    except socket.error:
        internet_available.return_value = False
    return internet_available.return_value
