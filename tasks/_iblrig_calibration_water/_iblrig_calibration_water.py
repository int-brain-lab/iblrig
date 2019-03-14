# !/usr/bin/python3
# -*- coding: utf-8 -*-

# automatic water calibration for pyBpod
# Anne Urai, CSHL, 2018
# Edited by Niccolo Bonacchi, CCU, 2018

import datetime
import re
import time
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy as sp
import seaborn as sns  # for easier plotting at the end
import serial
from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from ibllib.graphic import numinput

import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler

sph = SessionParamHandler(task_settings, user_settings)

bpod = Bpod()

# OUTPUT OVERVIEW FIGURE
sns.set()
sns.set_context(context="talk")
f, ax = plt.subplots(1, 2, sharex=False, figsize=(15, 7))

# TIME OF STARTING THE CALIBRATION
now = datetime.datetime.utcnow().astimezone().isoformat()
#  e.g. now = '2018-11-30T17:01:04.146888+00:00'
# >>> datetime.datetime.fromisoformat(now)
# datetime.datetime(2018, 11, 30, 17, 3, 51, 408746,
#                   tzinfo=datetime.timezone.utc)
# >>> datetime.datetime.fromisoformat(now).astimezone()
# datetime.datetime(2018, 11, 30, 17, 3, 51, 408746,
#                   tzinfo=datetime.timezone(datetime.timedelta(0), 'WET'))
print(now)

# =============================================================================
# OPEN THE VALVE FOR A SPECIFIED AMOUNT OF TIME
# =============================================================================


def water_drop(open_time, ntrials=100, iti=1, bpod='bpod_instance'):
    if bpod == 'bpod_instance':
        print('Need a Bpod instance to run a protocol')
        return 0

    # Start state machine definition
    for i in range(ntrials):

        sma = StateMachine(bpod)

        # open and close valve
        sma.add_state(
            state_name='reward',
            state_timer=open_time,
            state_change_conditions={'Tup': 'iti'},
            output_actions=[('Valve1', 255)])

        sma.add_state(
            state_name='iti',
            state_timer=iti,
            state_change_conditions={'Tup': 'exit'},
            output_actions=[])

        # Send state machine description to Bpod device and run
        bpod.send_state_machine(sma)
        bpod.run_state_machine(sma)
        # Get the timestamps of the implemented state machine ?
        # bpod.session.current_trial.export()


# =============================================================================
# READ INFO FROM THE OHAUS SCALE
# =============================================================================


def scale_read(COMport_string):
    # http://dmx.ohaus.com/WorkArea/downloadasset.aspx?id=3600
    # https://github.com/glansberry/ohaus_scale_data/blob/master/scale.py
    ser = serial.Serial(COMport_string, baudrate=9600,
                        timeout=3)  # open serial port

    # grab the software version and initialize
    ser.write(b'V\r\n')
    time.sleep(0.5)
    version = ser.readline()  # noqa

    # READ THE CURRENT WEIGHT
    ser.write(b'IP\r\n')  # ping the scale to print
    time.sleep(0.5)
    grams = ser.readline()

    # extract number
    grams = grams.decode("utf-8")
    grams = grams.strip("gN ")
    grams = re.findall(r"[-+]?\d*\.\d+|\d+", grams)
    grams = float(grams[0])
    # print('Reading Ohaus %s %fg' %(version.decode("utf-8"), grams))

    return grams

# =============================================================================
# FIRST, GENERATE A CALIBRATION CURVE - OPEN TIMES VS DROP SIZE
# see https://github.com/cortex-lab/Rigbox/blob/5d926cdafdfcb54cd74c77e152d158d3d837a90c/%2Bhw/calibrate.m  # noqa
# and https://github.com/sanworks/Bpod_Gen2/blob/14b78143e071c1cfda391b1754dba928ccc27792/Functions/Calibration/Liquid%20Reward/BpodLiquidCalibration.m  # noqa
# bpod wiki https://sites.google.com/site/bpoddocumentation/bpod-user-guide/liquid-calibration  # noqa
# =============================================================================


# initialize a dataframe with the results
df1 = pd.DataFrame(columns=["time", "open_time", "ndrops",
                            "mean_measured_weight", "std_measured_weight"])
ntrials = sph.NTRIALS
# in milliseconds, 10 to 100ms opening time
open_times = range(sph.MIN_OPEN_TIME, sph.MAX_OPEN_TIME, sph.STEP)
open_times = [i for i in range(
    sph.MIN_OPEN_TIME, sph.MAX_OPEN_TIME, sph.STEP) for _ in range(sph.PASSES)]

if sph.OAHUS_SCALE_PORT:
    stopweight = scale_read(sph.OAHUS_SCALE_PORT)
else:
    stopweight = numinput(f"Initialize weight",
                          "Enter the weight diplayed on the scale (gr):")

pass_ = 1
progress = 0
mw = []
for open_time in open_times:
    # Set the startweight to be the last recorded stopweight
    startweight = stopweight
    # Run the state machine; deliver ntrials drops of water
    water_drop(open_time / 1000, ntrials=ntrials, iti=sph.IPI, bpod=bpod)
    # wait for the scale update delay
    time.sleep(1)
    # Get the value
    if sph.OAHUS_SCALE_PORT:
        stopweight = scale_read(sph.OAHUS_SCALE_PORT)
    else:
        stopweight = numinput(f"{open_time}ms pass {pass_}",
                              "Enter the weight diplayed on the scale (gr):")
    # get the value of the amout of water delivered
    measured_weight = stopweight - startweight
    # summarize
    print(f'Weight change = {measured_weight}g |',
          f'delivered {measured_weight / ntrials * 1000}ul per',
          f'{open_time}ms (averaged over {ntrials} drops).')

    mw.append(measured_weight)

    if pass_ % sph.PASSES == 0:
        df1 = df1.append({
            "open_time": open_time,
            "ndrops": ntrials,
            "npasses": sph.PASSES,
            "mean_measured_weight": np.mean(mw),
            "std_measured_weight": np.std(mw),
            "time": datetime.datetime.now(),
        }, ignore_index=True)

        pass_ = 1
        mw = []
    else:
        pass_ += 1

    max_prog = len(open_times) * sph.PASSES
    progress += 1

    print(f'{progress / max_prog * 100}%',
          f'- Pass {pass_}/{sph.PASSES} @ {open_time}ms done.')

# SAVE
df1['open_time'] = df1['open_time'].astype("float")
df1['mean_measured_weight'] = df1['mean_measured_weight'].astype("float")
df1['ndrops'] = df1['ndrops'].astype("float")
df1["weight_perdrop"] = df1["mean_measured_weight"] / df1["ndrops"]
df1["weight_perdrop"] = df1["weight_perdrop"] * 1000  # in µl
if not df1.empty:
    df1.to_csv(sph.CALIBRATION_FUNCTION_FILE_PATH)

# FIT EXTRAPOLATION FUNCTION
time2vol = sp.interpolate.pchip(df1["open_time"], df1["weight_perdrop"])

xp = np.linspace(0, df1["open_time"].max(), ntrials * sph.PASSES)
ax[0].plot(xp, time2vol(xp), '-k')

# CALIBRATION CURVE
sns.scatterplot(x="open_time", y="weight_perdrop", data=df1, ax=ax[0])
ax[0].set(xlabel="Open time (ms)",
          ylabel="Measured volume (ul per drop)", title="Calibration curve")
title = f.suptitle(f"Water calibration {now}")
f.savefig(sph.CALIBRATION_CURVE_FILE_PATH)
os.system(sph.CALIBRATION_CURVE_FILE_PATH)
# =============================================================================
# ASK THE USER FOR A LINEAR RANGE
# =============================================================================
root = tk.Tk()
root.withdraw()
messagebox.showinfo(
    "Information",
    "Calibration curve completed! We're not done yet. \n \
    Please look at the figure and indicate a min - max range \n \
    over which the curve is monotonic. \n \
    The range of drop volumes should ideally be 1.5-3uL."
)
root.quit()
min_open_time = numinput(
    "Input",
    "What's the LOWEST opening time (in ms) of the linear (monotonic) range?")

max_open_time = numinput(
    "Input",
    "What's the HIGHEST opening time (in ms) of the linear (monotonic) range?")

ax[0].axvline(min_open_time, color='black')
ax[0].axvline(max_open_time, color='black')

f.savefig(sph.CALIBRATION_CURVE_FILE_PATH[:-4] + '_range.pdf')

# SAVE THE RANGE TOGETHER WITH THE CALIBRATION CURVE - SEPARATE FILE
df2 = pd.DataFrame.from_dict(
    {'min_open_time': min_open_time,
     'max_open_time': max_open_time,
     'index': [0]
     }
)
df2.to_csv(sph.CALIBRATION_RANGE_FILE_PATH)
os.system(sph.CALIBRATION_CURVE_FILE_PATH[:-4] + '_range.pdf')
bpod.close()
print(f'Completed water calibration {now}')

# Create flag
flag = Path(sph.SESSION_FOLDER) / 'transfer_me.flag'
open(flag, 'a').close()
flag2 = Path(sph.SESSION_FOLDER) / 'create_me.flag'
open(flag2, 'a').close()

root = tk.Tk()
root.withdraw()
messagebox.showinfo(
    "Information",
    "Calibration completed!\n\
    You can close the plots now."
)
root.quit()

if __name__ == '__main__':
    pass
    # root_data_folder = '/home/nico/Projects/IBL/github/iblrig_data/'
    # root_data_folder += 'Subjects'
    # session = '_iblrig_calibration/2018-11-28/4'
    # data_file = '/raw_behavior_data/_iblrig_calibration_water_function.csv'
    # df = pd.DataFrame.from_csv(os.path.join(root_data_folder, session,
    # data_file))
