# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, February 5th 2019, 4:11:13 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 5-02-2019 04:11:16.1616
import logging
import numpy as np
import pandas as pd
import scipy as sp
import scipy.interpolate
import ibllib.io.raw_data_loaders as raw

log = logging.getLogger('iblrig')


def init_reward_amount(sph) -> float:
    if not sph.ADAPTIVE_REWARD:
        return sph.REWARD_AMOUNT

    if sph.LAST_TRIAL_DATA is None:
        return sph.AR_INIT_VALUE
    elif sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA['trial_num'] < 200:  # noqa
        out = sph.LAST_TRIAL_DATA['reward_amount']
    elif sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA['trial_num'] >= 200:  # noqa
        out = sph.LAST_TRIAL_DATA['reward_amount'] - sph.AR_STEP
        out = sph.AR_MIN_VALUE if out <= sph.AR_MIN_VALUE else out

    if 'SUBJECT_WEIGHT' not in sph.LAST_SETTINGS_DATA.keys():
        return out

    previous_weight_factor = sph.LAST_SETTINGS_DATA['SUBJECT_WEIGHT'] / 25
    previous_water = sph.LAST_TRIAL_DATA['water_delivered'] / 1000

    if previous_water < previous_weight_factor:
        out = sph.LAST_TRIAL_DATA['reward_amount'] + sph.AR_STEP

    return out


def init_calib_func(sph):
    if not sph.AUTOMATIC_CALIBRATION:
        return

    if sph.LATEST_WATER_CALIBRATION_FILE:
        # Load last calibration df1
        df1 = pd.read_csv(sph.LATEST_WATER_CALIBRATION_FILE)
        # make interp func
        if df1.empty:
            msg = f"""
        ##########################################
                Water calibration file is emtpy!
        ##########################################"""
            log.error(msg)
            raise(ValueError)
        time2vol = scipy.interpolate.pchip(df1["open_time"],
                                           df1["weight_perdrop"])
        return time2vol
    else:
        return


def init_calib_func_range(sph) -> tuple:

    min_open_time = 0
    max_open_time = 1000
    msg = f"""
        ##########################################
            NOT FOUND: WATER RANGE CALIBRATION
        ##########################################
                        File empty
                 range set to (0, 1000)ms
        ##########################################"""

    if sph.LATEST_WATER_CALIB_RANGE_FILE:
        # Load last calibration r ange df1
        df1 = pd.read_csv(sph.LATEST_WATER_CALIB_RANGE_FILE)
        if not df1.empty:
            min_open_time = df1['min_open_time']
            max_open_time = df1['max_open_time']
        else:
            log.warning(msg)

    return min_open_time, max_open_time


def init_reward_valve_time(sph) -> float:
    # Calc reward valve time
    if not sph.AUTOMATIC_CALIBRATION:
        out = sph.CALIBRATION_VALUE / 3 * sph.REWARD_AMOUNT
    elif sph.AUTOMATIC_CALIBRATION and sph.CALIB_FUNC is not None:
        out = sph.CALIB_FUNC_RANGE[0]
        while np.round(sph.CALIB_FUNC(out), 3) < sph.REWARD_AMOUNT:
            out += 1
            if out >= sph.CALIB_FUNC_RANGE[1]:
                break
        out /= 1000
    elif sph.AUTOMATIC_CALIBRATION and sph.CALIB_FUNC is None:
        msg = """
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
        raise(ValueError)

    if out >= 1:
        msg = """
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
        raise(ValueError)

    return float(out)


def init_stim_gain(sph) -> float:
    if not sph.ADAPTIVE_GAIN:
        return sph.STIM_GAIN

    if sph.LAST_TRIAL_DATA and sph.LAST_TRIAL_DATA['trial_num'] >= 200:
        stim_gain = sph.AG_MIN_VALUE
    else:
        stim_gain = sph.AG_INIT_VALUE

    return stim_gain


def impulsive_control(sph):
    crit_1 = False  # 50% perf on one side ~100% on other
    crit_2 = False  # Median RT on hard (<50%) contrasts < 300ms
    crit_3 = False  # Getting enough water
    data = raw.load_data(sph.PREVIOUS_SESSION_PATH)
    if data is None or not data:
        return sph

    signed_contrast = np.array([x['signed_contrast'] for x in data])
    trial_correct = np.array([x['trial_correct'] for x in data])

    # Check crit 1
    l_trial_correct = trial_correct[signed_contrast < 0]
    r_trial_correct = trial_correct[signed_contrast > 0]
    if len(l_trial_correct) == 0 or len(r_trial_correct) == 0:
        return sph

    p_left = sum(l_trial_correct) / len(l_trial_correct)
    p_righ = sum(r_trial_correct) / len(r_trial_correct)
    if np.abs(p_left - p_righ) >= 0.4:
        crit_1 = True

    # Check crit 2
    rt = np.array([
        x['behavior_data']['States timestamps']['closed_loop'][0][1] -
        x['behavior_data']['States timestamps']['stim_on'][0][0] for x in data]
    )
    if sp.median(rt[np.abs(signed_contrast) < 0.5]) < 0.3:
        crit_2 = True
    # Check crit 3
    previous_weight_factor = sph.LAST_SETTINGS_DATA['SUBJECT_WEIGHT'] / 25
    previous_water = sph.LAST_TRIAL_DATA['water_delivered'] / 1000

    if previous_water >= previous_weight_factor:
        crit_3 = True

    if crit_1 and crit_2 and crit_3:
        # Reward decrease
        sph.REWARD_AMOUNT -= sph.AR_STEP  # 0.1 µl
        if sph.REWARD_AMOUNT < sph.AR_MIN_VALUE:
            sph.REWARD_AMOUNT = sph.AR_MIN_VALUE
        # Increase timeout error
        sph.ITI_ERROR = 3.
        # Introduce interactive delay
        sph.INTERACTIVE_DELAY = 0.250  # sec
        sph.IMPULSIVE_CONTROL = 'ON'

    return sph


if __name__ == "__main__":
    sess_path = ('/home/nico/Projects/IBL/IBL-github/iblrig' +
                 '/scratch/test_iblrig_data/Subjects/ZM_335/2018-12-13/001')
    data = raw.load_data(sess_path)
