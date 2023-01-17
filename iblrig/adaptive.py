#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Tuesday, February 5th 2019, 4:11:13 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-01-24
"""
Calibration tests and reward configurations
"""
import logging

import numpy as np
import scipy as sp
from iblrig.raw_data_loaders import load_data

log = logging.getLogger("iblrig")


def init_stim_gain(sph: object) -> float:
    if not sph.ADAPTIVE_GAIN:
        return sph.STIM_GAIN

    if sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA["trial_num"] >= 200:
        stim_gain = sph.AG_MIN_VALUE
    else:
        stim_gain = sph.AG_INIT_VALUE

    return stim_gain


def impulsive_control(sph: object):
    crit_1 = False  # 50% perf on one side ~100% on other
    crit_2 = False  # Median RT on hard (<50%) contrasts < 300ms
    crit_3 = False  # Getting enough water
    data = load_data(sph.PREVIOUS_SESSION_PATH)  # Loads data of previous session
    if data is None or not data:
        return sph

    signed_contrast = np.array([x["signed_contrast"] for x in data])
    trial_correct = np.array([x["trial_correct"] for x in data])

    # Check crit 1
    l_trial_correct = trial_correct[signed_contrast < 0]
    r_trial_correct = trial_correct[signed_contrast > 0]
    # If no trials on either side crit1 would be false and last check not pass, safe to return
    if len(l_trial_correct) == 0 or len(r_trial_correct) == 0:
        return sph

    p_left = sum(l_trial_correct) / len(l_trial_correct)
    p_righ = sum(r_trial_correct) / len(r_trial_correct)
    if np.abs(p_left - p_righ) >= 0.4:
        crit_1 = True

    # Check crit 2
    rt = np.array(
        [
            x["behavior_data"]["States timestamps"]["closed_loop"][0][1]
            - x["behavior_data"]["States timestamps"]["stim_on"][0][0]
            for x in data
        ]
    )
    if sp.median(rt[np.abs(signed_contrast) < 0.5]) < 0.3:
        crit_2 = True
    # Check crit 3
    previous_weight_factor = sph.LAST_SETTINGS_DATA["SUBJECT_WEIGHT"] / 25
    previous_water = sph.LAST_TRIAL_DATA["water_delivered"] / 1000

    if previous_water >= previous_weight_factor:
        crit_3 = True

    if crit_1 and crit_2 and crit_3:
        # Reward decrease
        sph.REWARD_AMOUNT -= sph.AR_STEP  # 0.1 µl
        if sph.REWARD_AMOUNT < sph.AR_MIN_VALUE:
            sph.REWARD_AMOUNT = sph.AR_MIN_VALUE
        # Increase timeout error
        sph.ITI_ERROR = 3.0
        # Introduce interactive delay
        sph.INTERACTIVE_DELAY = 0.250  # sec
        sph.IMPULSIVE_CONTROL = "ON"

    return sph
