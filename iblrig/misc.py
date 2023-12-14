"""
Provides collection of functionality used throughout the iblrig repository.

Assortment of functions, frequently used, but without a great deal of commonality. Functions can,
and should, be broken out into their own files and/or classes as the organizational needs of this
repo change over time.
"""
import argparse
import datetime
from pathlib import Path
from typing import Literal

import numpy as np

from iblutil.util import setup_logger

FLAG_FILE_NAMES = [
    'transfer_me.flag',
    'create_me.flag',
    'poop_count.flag',
    'passive_data_for_ephys.flag',
]

log = setup_logger('iblrig')


def _get_task_argument_parser(parents=None):
    """
    This function returns the task argument parser with extra optional parameters if provided
    This function is kept separate from parsing for unit tests purposes.
    """
    parser = argparse.ArgumentParser(parents=parents or [])
    parser.add_argument('-s', '--subject', required=True, help='--subject ZFM-05725')
    parser.add_argument('-u', '--user', required=False, default=None, help='alyx username to register the session')
    parser.add_argument(
        '-p',
        '--projects',
        nargs='+',
        default=[],
        help="project name(s), something like 'psychedelics' or 'ibl_neuropixel_brainwide_01'; if specify "
        'multiple projects, use a space to separate them',
    )
    parser.add_argument(
        '-c',
        '--procedures',
        nargs='+',
        default=[],
        help="long description of what is occurring, something like 'Ephys recording with acute probe(s)'; "
        'be sure to use the double quote characters to encapsulate the description and a space to separate '
        'multiple procedures',
    )
    parser.add_argument('-w', '--weight', type=float, dest='subject_weight_grams', required=False, default=None)
    parser.add_argument('--no-interactive', dest='interactive', action='store_false')
    parser.add_argument('--append', dest='append', action='store_true')
    parser.add_argument('--stub', type=Path, help='Path to _ibl_experiment.description.yaml stub file.')
    parser.add_argument(
        '--log-level',
        default='INFO',
        help='verbosity of the console logger (default: INFO)',
        choices=['NOTSET', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'],
    )
    parser.add_argument('--wizard', dest='wizard', action='store_true')
    return parser


def _post_parse_arguments(**kwargs):
    """
    This is called to post-process the arguments after parsing. It is used to force the interactive
    mode to True (as it is a call from a user) and to override the settings file value for the user.
    This function is split for unit-test purposes.
    :param kwargs:
    :return:
    """
    # if the user is specified, then override the settings file value
    user = kwargs.pop('user')
    if user is not None:
        kwargs['iblrig_settings'] = {'ALYX_USER': user}
    return kwargs


def get_task_arguments(parents=None):
    """
    This function parses input to run the tasks. All the variables are fed to the Session instance
    task.py -s subject_name -p projects_name -c procedures_name --no-interactive
    :param extra_args: list of dictionaries of additional argparse arguments to add to the parser
        For example, to add a new toto and titi arguments, use:
        get_task_arguments({'--toto', type=str, default='toto'}, {'--titi', action='store_true', default=False})
    :return:
    """
    parser = _get_task_argument_parser(parents=parents)
    kwargs = vars(parser.parse_args())
    return _post_parse_arguments(**kwargs)


def _is_datetime(x: str) -> bool:
    """
    Check if a string is a date in the format YYYY-MM-DD.

    Parameters
    ----------
    x : str
        The string to check.

    Returns
    -------
    bool or None
        True if the string matches the date format, False otherwise, or None if there's an exception.
    """
    try:
        datetime.strptime(x, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def get_session_path(path: str | Path) -> Path | None:
    """Returns the session path from any filepath if the date/number
    pattern is found"""
    if path is None:
        return
    if isinstance(path, str):
        path = Path(path)
    sess = None
    for i, p in enumerate(path.parts):
        if p.isdigit() and _is_datetime(path.parts[i - 1]):
            sess = Path().joinpath(*path.parts[: i + 1])

    return sess


def get_port_events(events: dict, name: str = '') -> list:
    out: list = []
    for k in events:
        if name in k:
            out.extend(events[k])
    out = sorted(out)

    return out


def truncated_exponential(scale: float = 0.35, min_value: float = 0.2, max_value: float = 0.5) -> float:
    """
    Generate a truncated exponential random variable within a specified range.

    Parameters
    ----------
    scale : float, optional
        Scale of the exponential distribution (inverse of rate parameter). Defaults to 0.35.
    min_value : float, optional
        Minimum value for the truncated range. Defaults to 0.2.
    max_value : float, optional
        Maximum value for the truncated range. Defaults to 0.5.

    Returns
    -------
    float
        Truncated exponential random variable.

    Notes
    -----
    This function generates a random variable from an exponential distribution
    with the specified `scale`. It then checks if the generated value is within
    the specified range `[min_value, max_value]`. If it is within the range, it returns
    the generated value; otherwise, it recursively generates a new value until it falls
    within the specified range.

    The `scale` should typically be greater than or equal to the `min_value` to avoid
    potential issues with infinite recursion.
    """
    x = np.random.exponential(scale)
    if min_value <= x <= max_value:
        return x
    else:
        return truncated_exponential(scale, min_value, max_value)


def get_biased_probs(n: int, idx: int = -1, p_idx: float = 0.5) -> list[float]:
    """
    Calculate biased probabilities for all elements of an array such that the
    `i`th value has probability `p_i` for being drawn relative to the remaining
    values.

    See: https://github.com/int-brain-lab/iblrig/issues/74

    Parameters
    ----------
    n : int
        The length of the array, i.e., the number of probabilities to generate.
    idx : int, optional
        The index of the value that has the biased probability. Defaults to -1.
    p_idx : float, optional
        The probability of the `idx`-th value relative to the rest. Defaults to 0.5.

    Returns
    -------
    List[float]
        List of biased probabilities.

    Raises
    ------
    IndexError
        If `idx` is out of range
    ValueError
        If `p_idx` is 0.
    """
    if n == 1:
        return [1.0]
    if idx not in range(-n, n):
        raise IndexError('`idx` is out of range.')
    if p_idx == 0:
        raise ValueError('Probability must be larger than 0.')
    z = n - 1 + p_idx
    p = [1 / z] * n
    p[idx] *= p_idx
    return p


def draw_contrast(
    contrast_set: list[float],
    probability_type: Literal['skew_zero', 'biased', 'uniform'] = 'biased',
    idx: int = -1,
    idx_probability: float = 0.5,
) -> float:
    """
    Draw a contrast value from a given iterable based to the specified probability type

    Parameters
    ----------
    contrast_set : list[float]
        The set of contrast values from which to draw.
    probability_type : Literal["skew_zero", "biased", "uniform"], optional
        The type of probability distribution to use.
        - "skew_zero" or "biased": Draws with a biased probability distribution based on idx and idx_probability,
        - "uniform": Draws with a uniform probability distribution.
        Defaults to "biased".
    idx : int, optional
        Index for probability manipulation (with "skew_zero" or "biased"), default: -1.
    idx_probability : float, optional
        Probability for the specified index (with "skew_zero" or "biased"), default: 0.5.

    Returns
    -------
    float
        The drawn contrast value.

    Raises
    ------
    ValueError
        If an unsupported `probability_type` is provided.
    """
    if probability_type in ['skew_zero', 'biased']:
        p = get_biased_probs(n=len(contrast_set), idx=idx, p_idx=idx_probability)
        return np.random.choice(contrast_set, p=p)
    elif probability_type == 'uniform':
        return np.random.choice(contrast_set)
    else:
        raise ValueError("Unsupported probability_type. Use 'skew_zero', 'biased', or 'uniform'.")


def online_std(new_sample: float, new_count: int, old_mean: float, old_std: float) -> tuple[float, float]:
    """
    Updates the mean and standard deviation of a group of values after a sample update

    Parameters
    ----------
    new_sample : float
        The new sample to be included.
    new_count : int
        The new count of samples (including new_sample).
    old_mean : float
        The previous mean (N - 1).
    old_std : float
        The previous standard deviation (N - 1).

    Returns
    -------
    tuple[float, float]
        Updated mean and standard deviation.
    """
    if new_count == 1:
        return new_sample, 0.0
    new_mean = (old_mean * (new_count - 1) + new_sample) / new_count
    new_std = np.sqrt((old_std**2 * (new_count - 1) + (new_sample - old_mean) * (new_sample - new_mean)) / new_count)
    return new_mean, new_std
