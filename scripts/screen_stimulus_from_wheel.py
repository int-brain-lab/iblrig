import math
import alf.io
from one.api import ONE
import numpy as np


WHEEL_RADIUS = 31
USER_DEFINED_GAIN = 4.0
MM_PER_DEG = (2 * math.pi * WHEEL_RADIUS) / 360
GAIN_FACTOR = 1 / (MM_PER_DEG * USER_DEFINED_GAIN)


def pos_on_screen(pos, init_pos):
    try:
        iter(pos)
    except TypeError:
        pos = [pos]

    for p in pos:
        yield (((p / GAIN_FACTOR) + init_pos) + 180) % 360 - 180


def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx


def get_stim_from_wheel(eid, tr):
    """
    for a given session (eid) and trial (tr)
    return the position of the stimulus on the screen,
    where the one screen side is at 35 and the other at -35.

    If the mouse wheels wrongly away from 0, the stimulus
    remains at the edge of the screen
    """

    # eid = '83e77b4b-dfa0-4af9-968b-7ea0c7a0c7e4'
    # tr = 0
    # For a given trial tr, the stim on screen responds to the wheel between
    # trials['goCue_times'][tr] and trials['feedback_times'][tr]

    one = ONE()
    dataset_types = [
        "trials.goCue_times",
        "trials.feedback_times",
        "trials.feedbackType",
        "trials.contrastLeft",
        "trials.contrastRight",
        "trials.choice",
    ]

    one.load(eid, dataset_types=dataset_types, dclass_output=True)
    alf_path = one.path_from_eid(eid) / "alf"
    trials = alf.io.load_object(alf_path, "trials")
    wheel = one.load_object(eid, "wheel")

    # check where stimulus started for initial shift
    if np.isnan(trials["contrastLeft"][tr]):
        init_pos = -35
    else:
        init_pos = 35

    # the screen stim is only coupled to the wheel in this time
    wheel_start_idx = find_nearest(wheel.timestamps, trials["goCue_times"][tr])
    wheel_end_idx = find_nearest(wheel.timestamps, trials["feedback_times"][tr])
    wheel_pos = wheel.position[wheel_start_idx:wheel_end_idx]
    wheel_times = wheel.timestamps[wheel_start_idx:wheel_end_idx]

    wheel_pos = wheel_pos * 180 / np.pi
    wheel_pos = wheel_pos - wheel_pos[0]  # starting at 0

    screen_deg = np.array(list(pos_on_screen(wheel_pos, init_pos)))
    # set screen degrees to initial value if larger than 35
    # as then the stimulus stays at the edge of the screen
    idc = np.where(abs(screen_deg) > 35)[0]

    screen_deg[idc] = screen_deg[0]

    # f = interp1d(wheel_times, absolute_screen_deg)
    # as you might want to get values as shown on screen, i.e. at 60 Hz

    return wheel_pos, screen_deg, trials["feedbackType"][tr], wheel_times
