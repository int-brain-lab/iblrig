#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Friday, February 8th 2019, 12:51:51 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
"""
Provides collection of functionality used throughout the iblrig repository.

Assortment of functions, frequently used, but without a great deal of commonality. Functions can,
and should, be broken out into their own files and/or classes as the organizational needs of this
repo change over time.
"""
import datetime
import json
import logging
import shutil
from pathlib import Path
from typing import Optional, Union

import numpy as np

from iblrig.raw_data_loaders import load_settings

FLAG_FILE_NAMES = [
    "transfer_me.flag",
    "create_me.flag",
    "poop_count.flag",
    "passive_data_for_ephys.flag",
]

log = logging.getLogger("iblrig")


def _isdatetime(x: str) -> Optional[bool]:
    """
    Check if string is a date in the format YYYY-MM-DD.

    :param x: The string to check
    :return: True if the string matches the date format, False otherwise.
    :rtype: Optional[bool]
    """
    try:
        datetime.strptime(x, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def get_session_path(path: Union[str, Path]) -> Optional[Path]:
    """Returns the session path from any filepath if the date/number
    pattern is found"""
    if path is None:
        return
    if isinstance(path, str):
        path = Path(path)
    sess = None
    for i, p in enumerate(path.parts):
        if p.isdigit() and _isdatetime(path.parts[i - 1]):
            sess = Path().joinpath(*path.parts[: i + 1])

    return sess


def check_transfer(src_session_path: str, dst_session_path: str):
    """
    Check all the files in the source directory match those in the destination directory.
    :param src_session_path: The source directory that was copied
    :param dst_session_path: The copy target directory
    :return:
    """
    src_files = sorted([x for x in Path(src_session_path).rglob("*") if x.is_file()])
    dst_files = sorted([x for x in Path(dst_session_path).rglob("*") if x.is_file()])
    assert len(src_files) == len(dst_files), "Not all files transferred"
    for s, d in zip(src_files, dst_files):
        assert s.name == d.name, "file name mismatch"
        assert s.stat().st_size == d.stat().st_size, "file size mismatch"


def transfer_folder(src: Path, dst: Path, force: bool = False) -> None:
    print(f"Attempting to copy:\n{src}\n--> {dst}")
    if force:
        print(f"Removing {dst}")
        shutil.rmtree(dst, ignore_errors=True)
    print(f"Copying all files:\n{src}\n--> {dst}")
    shutil.copytree(src, dst)
    # If folder was created delete the src_flag_file
    if check_transfer(src, dst) is None:
        print("All files copied")


def smooth_rolling_window(x, window_len=11, window="blackman"):
    """
    Smooth the data using a window with requested size.

    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal
    (with the window size) in both ends so that transient parts are minimized
    in the beginning and end part of the output signal.

    :param x: The input signal
    :type x: list or numpy.array
    :param window_len: The dimension of the smoothing window,
                       should be an **odd** integer, defaults to 11
    :type window_len: int, optional
    :param window: The type of window from ['flat', 'hanning', 'hamming',
                   'bartlett', 'blackman']
                   flat window will produce a moving average smoothing,
                   defaults to 'blackman'
    :type window: str, optional
    :raises ValueError: Smooth only accepts 1 dimension arrays.
    :raises ValueError: Input vector needs to be bigger than window size.
    :raises ValueError: Window is not one of 'flat', 'hanning', 'hamming',
                        'bartlett', 'blackman'
    :return: Smoothed array
    :rtype: numpy.array
    """
    # **NOTE:** length(output) != length(input), to correct this:
    # return y[(window_len/2-1):-(window_len/2)] instead of just y.
    if isinstance(x, list):
        x = np.array(x)

    if x.ndim != 1:
        raise ValueError("smooth only accepts 1 dimension arrays.")

    if x.size < window_len:
        raise ValueError("Input vector needs to be bigger than window size.")

    if window_len < 3:
        return x

    if window not in ["flat", "hanning", "hamming", "bartlett", "blackman"]:
        raise ValueError(
            "Window is not one of 'flat', 'hanning', 'hamming',\
'bartlett', 'blackman'"
        )

    s = np.r_[x[window_len - 1 : 0 : -1], x, x[-1:-window_len:-1]]
    # print(len(s))
    if window == "flat":  # moving average
        w = np.ones(window_len, "d")
    else:
        w = eval("np." + window + "(window_len)")

    y = np.convolve(w / w.sum(), s, mode="valid")
    return y[round((window_len / 2 - 1)) : round(-(window_len / 2))]


def checkerboard(shape):
    return np.indices(shape).sum(axis=0) % 2


def make_square_dvamat(size, dva):
    c = np.arange(size) - int(size / 2)
    x = np.array([c] * 15)
    y = np.rot90(x)
    dvamat = np.array(list(zip(y.ravel() * dva, x.ravel() * dva)), dtype="int, int").reshape(
        x.shape
    )
    return dvamat


def get_port_events(events: dict, name: str = "") -> list:
    out: list = []
    for k in events:
        if name in k:
            out.extend(events[k])
    out = sorted(out)

    return out


def update_buffer(buffer: list, val) -> list:
    buffer = np.roll(buffer, -1, axis=0)
    buffer[-1] = val
    return buffer.tolist()


def texp(factor: float = 0.35, min_: float = 0.2, max_: float = 0.5) -> float:
    """Truncated exponential
    mean = 0.35
    min = 0.2
    max = 0.5
    """
    x = np.random.exponential(factor)
    if min_ <= x <= max_:
        return x
    else:
        return texp(factor=factor, min_=min_, max_=max_)


def get_biased_probs(n: int, idx: int = -1, prob: float = 0.5) -> list:
    """
    get_biased_probs [summary]

    Calculate the biased probability for all elements of an array so that
    the <idx> value has <prob> probability of being drawn in respect to the
    remaining values.
    https://github.com/int-brain-lab/iblrig/issues/74
    For prob == 0.5
    p = [2 / (2 * len(contrast_set) - 1) for x in contrast_set]
    p[-1] *= 1 / 2
    For arbitrary probs
    p = [1/(n-1 + 0.5)] * (n - 1)

    e.g. get_biased_probs(3, idx=-1, prob=0.5)
    >>> [0.4, 0.4, 0.2]

    :param n: The length of the array, i.e. the num of probas to generate
    :type n: int
    :param idx: The index of the value that has the biased probability,
                defaults to -1
    :type idx: int, optional
    :param prob: The probability of the idxth value relative top the rest,
                 defaults to 0.5
    :type prob: float, optional
    :return: List of biased probabilities
    :rtype: list

    """
    n_1 = n - 1
    z = n_1 + prob
    p = [1 / z] * (n_1 + 1)
    p[idx] *= prob
    return p


def draw_contrast(
    contrast_set: list, prob_type: str = "biased", idx: int = -1, idx_prob: float = 0.5
) -> float:
    if prob_type == "biased":
        p = get_biased_probs(len(contrast_set), idx=idx, prob=idx_prob)
        return np.random.choice(contrast_set, p=p)
    elif prob_type == "uniform":
        return np.random.choice(contrast_set)


def check_stop_criterions(init_datetime, rt_buffer, trial_num) -> int:
    # STOPPING CRITERIONS
    # < than 400 trials in 45 minutes
    time_up = init_datetime + datetime.timedelta(minutes=45)
    if time_up <= datetime.datetime.now() and trial_num <= 400:
        return 1

    # Median response time of latest N = 20 trials > than 5 times
    # the median response time and more than 400 trials performed
    N, T = 20, 400
    if len(rt_buffer) >= N and trial_num > T:
        latest_median = np.median(rt_buffer[-N:])
        all_median = np.median(rt_buffer)

        if latest_median > all_median * 5:
            return 2

    end_time = init_datetime + datetime.timedelta(minutes=90)
    if end_time <= datetime.datetime.now():
        return 3

    return False


def get_trial_rt(behavior_data: dict) -> float:
    return (
        behavior_data["States timestamps"]["closed_loop"][0][1]
        - behavior_data["States timestamps"]["stim_on"][0][0]
    )


def create_flag(session_folder_path: str, flag: str) -> None:
    if not flag.endswith(".flag"):
        flag = flag + ".flag"
    if flag not in FLAG_FILE_NAMES:
        log.warning(f"Creating unknown flag file {flag} in {session_folder_path}")

    path = Path(session_folder_path) / flag
    open(path, "a").close()


def create_flags(data_file_path: str, poop_count: bool) -> None:
    session_folder_path = Path(data_file_path).parent.parent
    create_flag(session_folder_path, "transfer_me")
    create_flag(session_folder_path, "create_me")
    if poop_count:
        create_flag(session_folder_path, "poop_count")


def draw_session_order():
    first = list(range(0, 4))
    second = list(range(4, 8))
    third = list(range(8, 12))
    for x in [first, second, third]:
        np.random.shuffle(x)
    first.extend(second)
    first.extend(third)

    return first


def patch_settings_file(sess_or_file: str, patch: dict) -> None:
    sess_or_file = Path(sess_or_file)
    if sess_or_file.is_file() and sess_or_file.name.endswith("_iblrig_taskSettings.raw.json"):
        session = sess_or_file.parent.parent
        file = sess_or_file
    elif sess_or_file.is_dir() and sess_or_file.name.isdecimal():
        file = sess_or_file / "raw_behavior_data" / "_iblrig_taskSettings.raw.json"
        session = sess_or_file
    else:
        print("not a settings file or a session folder")
        return

    settings = load_settings(session)
    settings.update(patch)
    # Rename file on disk keeps pathlib ref to "file" intact
    file.rename(file.with_suffix(".json_bk"))
    with open(file, "w") as f:
        f.write(json.dumps(settings, indent=1))
        f.write("\n")
        f.flush()
    # Check if properly saved
    saved_settings = load_settings(session)
    if settings == saved_settings:
        file.with_suffix(".json_bk").unlink()
    return


# TODO: Consider migrating this to ephys_session_file_creator
def generate_position_contrasts(
    contrasts: list = [1.0, 0.25, 0.125, 0.0625],
    positions: list = [-35, 35],
    cp_repeats: int = 20,
    shuffle: bool = True,
    to_string: bool = False,
):
    """generate_position_contrasts generate contrasts and positions

    :param contrasts: Set of contrasts in floats, defaults to [1.0, 0.25, 0.125, 0.0625]
    :type contrasts: list, optional
    :param positions: Set of positions in int, defaults to [-35, 35]
    :type positions: list, optional
    :param cp_repeats: Number of repetitions for each contrast position pair, defaults to 20
    :type cp_repeats: int, optional
    :param shuffle: Shuffle the result or return sorted, defaults to True
    :type shuffle: bool, optional
    :param to_string: Return strings instead of int/float pairs, defaults to False
    :type to_string: bool, optional
    :return: 2D array with positions and contrasts
    :rtype: numpy.array()
    """
    # Generate a set of positions and contrasts
    pos = sorted(positions * len(contrasts) * cp_repeats)
    cont = contrasts * cp_repeats * 2

    data = np.array([[int(p), c] for p, c in zip(pos, cont)])
    if shuffle:
        np.random.shuffle(data)
    if to_string:
        data = np.array([[str(int(p)), str(c)] for p, c in data])
    return data


if __name__ == "__main__":
    get_biased_probs(4)
    print(draw_contrast([1, 2, 3]))
    print(draw_contrast([1, 2, 3, 4, 5]))
    print(draw_contrast([1, 2, 3, 4, 5, 6, 7]))
    print(draw_contrast([1, 2, 3], prob=0.3, idx=0))
    print(draw_contrast([1, 2, 3, 4, 5], prob=0.5, idx=0))
    print(draw_contrast([1, 2, 3, 4, 5, 6, 7], prob=0.3, idx=-1))
