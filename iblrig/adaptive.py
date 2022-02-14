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
import scipy.interpolate

import iblrig.params as params
from iblrig.raw_data_loaders import load_data

log = logging.getLogger("iblrig")


def init_reward_amount(sph: object) -> float:
    if not sph.ADAPTIVE_REWARD:
        return sph.REWARD_AMOUNT

    if sph.LAST_TRIAL_DATA is None:
        return sph.AR_INIT_VALUE
    elif sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA["trial_num"] < 200:
        out = sph.LAST_TRIAL_DATA["reward_amount"]
    elif sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA["trial_num"] >= 200:
        out = sph.LAST_TRIAL_DATA["reward_amount"] - sph.AR_STEP
        out = sph.AR_MIN_VALUE if out <= sph.AR_MIN_VALUE else out

    if "SUBJECT_WEIGHT" not in sph.LAST_SETTINGS_DATA.keys():
        return out

    previous_weight_factor = sph.LAST_SETTINGS_DATA["SUBJECT_WEIGHT"] / 25
    previous_water = sph.LAST_TRIAL_DATA["water_delivered"] / 1000

    if previous_water < previous_weight_factor:
        out = sph.LAST_TRIAL_DATA["reward_amount"] + sph.AR_STEP

    out = sph.AR_MAX_VALUE if out > sph.AR_MAX_VALUE else out
    return out


def init_calib_func() -> scipy.interpolate.pchip:
    PARAMS = params.load_params_file()
    if PARAMS["WATER_CALIBRATION_DATE"] == "":
        msg = """
    ##########################################
         Water calibration date is emtpy!
    ##########################################"""
        log.error(msg)
        raise ValueError("Rig not calibrated")

    time2vol = scipy.interpolate.pchip(
        PARAMS["WATER_CALIBRATION_OPEN_TIMES"], PARAMS["WATER_CALIBRATION_WEIGHT_PERDROP"],
    )

    return time2vol


def init_calib_func_range() -> tuple:
    PARAMS = params.load_params_file()
    if PARAMS["WATER_CALIBRATION_RANGE"] == "":
        min_open_time = 0
        max_open_time = 1000
        msg = """
            ##########################################
                NO DATA: WATER CALIBRATION RANGE
            ##########################################
                        using full range
            ##########################################"""
        log.warning(msg)
    else:
        min_open_time = PARAMS["WATER_CALIBRATION_RANGE"][0]
        max_open_time = PARAMS["WATER_CALIBRATION_RANGE"][1]

    return min_open_time, max_open_time


def calc_reward_valve_time(
    reward_amount: float, calib_func: scipy.interpolate.pchip, calib_func_range: tuple
) -> float:
    valve_time = calib_func_range[0]
    while np.round(calib_func(valve_time), 3) < reward_amount:
        valve_time += 1
        if valve_time >= calib_func_range[1]:
            break
    valve_time /= 1000
    return valve_time


def manual_reward_valve_time(reward_amount: float, calibration_value: float) -> float:
    return calibration_value / 3 * reward_amount


def init_reward_valve_time(sph: object) -> float:
    # Calc reward valve time
    if not sph.AUTOMATIC_CALIBRATION:
        out = manual_reward_valve_time(sph.REWARD_AMOUNT, sph.CALIBRATION_VALUE)
    elif sph.AUTOMATIC_CALIBRATION and sph.CALIB_FUNC is not None:
        out = calc_reward_valve_time(sph.REWARD_AMOUNT, sph.CALIB_FUNC, sph.CALIB_FUNC_RANGE)
    elif sph.AUTOMATIC_CALIBRATION and sph.CALIB_FUNC is None:
        msg = f"""
        ##########################################
                NO CALIBRATION FILE WAS FOUND:
        Calibrate the rig or use a manual calibration
        PLEASE GO TO:
        iblrig_params/IBL/tasks/{sph.PYBPOD_PROTOCOL}/task_settings.py
        and set:
            AUTOMATIC_CALIBRATION = False
            CALIBRATION_VALUE = <MANUAL_CALIBRATION>
        ##########################################"""
        log.error(msg)
        raise ValueError

    if out >= 1:
        msg = f"""
        ##########################################
            REWARD VALVE TIME IS TOO HIGH!
        Probably because of a BAD calibration file
        Calibrate the rig or use a manual calibration
        PLEASE GO TO:
        iblrig_params/IBL/tasks/{sph.PYBPOD_PROTOCOL}/task_settings.py
        and set:
            AUTOMATIC_CALIBRATION = False
            CALIBRATION_VALUE = <MANUAL_CALIBRATION>
        ##########################################"""
        log.error(msg)
        raise ValueError

    return float(out)


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


if __name__ == "__main__":
    sess_path = (
        "/home/nico/Projects/IBL/github/iblrig"
        + "/scratch/test_iblrig_data/Subjects/ZM_335/2018-12-13/001"
    )
    data = load_data(sess_path)
    sess_path = "/mnt/s0/IntegrationTests/Subjects_init/_iblrig_calibration/2019-02-21/003/raw_behavior_data"  # noqa

    init_calib_func_range()
