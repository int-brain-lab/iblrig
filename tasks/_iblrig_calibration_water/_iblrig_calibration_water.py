# !/usr/bin/python3
# -*- coding: utf-8 -*-

# automatic water calibration for pyBpod
# Anne Urai, CSHL, 2018
# Edited by Niccolo Bonacchi, CCU, 2018

import datetime
import glob  # https://pyserial.readthedocs.io/en/latest/shortintro.html
import json
import os
import re
import time
# for dialog box
#import tkinter as tk
from tkinter import messagebox, simpledialog

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy as sp
import seaborn as sns  # for easier plotting at the end
# ask Nicco if I need to separately import these?
import serial
from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine

import user_settings  # PyBpod creates this file on run.
import task_settings
# import pybpod_projects.IBL.tasks._iblrig_calibration_water._user_settings as user_settings
from session_params import SessionParamHandler
# from pybpod_projects.IBL.tasks._iblrig_calibration_water.session_params import SessionParamHandler

sph = SessionParamHandler(task_settings, user_settings)

bpod = Bpod()

# OUTPUT OVERVIEW FIGURE
sns.set()
sns.set_context(context="talk")
f, ax = plt.subplots(1, 2, sharex=False, figsize=(15, 7))

# TIME OF STARTING THE CALIBRATION
now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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
    version = ser.readline()

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


def numinput(title, prompt, default=None, minval=None, maxval=None):
    """Pop up a dialog window for input of a number.
    Arguments:
    title: is the title of the dialog window,
    prompt: is a text mostly describing what numerical information to input.
    default: default value
    minval: minimum value for imput
    maxval: maximum value for input

    The number input must be in the range minval .. maxval if these are
    given. If not, a hint is issued and the dialog remains open for
    correction. Return the number input.
    If the dialog is canceled,  return None.

    Example:
    >>> numinput("Poker", "Your stakes:", 1000, minval=10, maxval=10000)
    """
    return simpledialog.askfloat(title, prompt, initialvalue=default,
                                 minvalue=minval, maxvalue=maxval)

# =============================================================================
# FIRST, GENERATE A CALIBRATION CURVE - OPEN TIMES VS DROP SIZE
# see https://github.com/cortex-lab/Rigbox/blob/5d926cdafdfcb54cd74c77e152d158d3d837a90c/%2Bhw/calibrate.m
# and https://github.com/sanworks/Bpod_Gen2/blob/14b78143e071c1cfda391b1754dba928ccc27792/Functions/Calibration/Liquid%20Reward/BpodLiquidCalibration.m
# bpod wiki https://sites.google.com/site/bpoddocumentation/bpod-user-guide/liquid-calibration
# =============================================================================


# initialize a dataframe with the results
df1 = pd.DataFrame(columns=["time", "open_time", "ndrops", "measured_weight"])
ntrials = sph.NTRIALS
# in milliseconds, 10 to 100ms opening time
open_times = range(sph.MIN_OPEN_TIME, sph.MAX_OPEN_TIME, sph.STEP)
stopweight = 0

for open_time in open_times:
    time.sleep(1)
    if sph.OAHUS_SCALE_PORT:
        startweight = scale_read(sph.OAHUS_SCALE_PORT)
    else:
        startweight = stopweight
		# startweight = numinput(f"Start Weight (gr) [{open_time}ms]",
        #                        "Enter the starting weight diplayed on the scale (gr):", default=stopweight)
    # Run the state machine
    water_drop(open_time/1000, ntrials=ntrials, iti=sph.IPI,
               bpod=bpod)  # deliver ntrials drops of water
    time.sleep(1)

    if sph.OAHUS_SCALE_PORT:
        stopweight = scale_read(sph.OAHUS_SCALE_PORT)
    else:
        stopweight = numinput(f"End Weight (gr) [{open_time}ms]",
                              "Enter the final weight diplayed on the scale (gr):")

    measured_weight = stopweight - startweight
    # summarize
    print(f'Weight change = {measured_weight}g |',
          f'delivered {measured_weight / ntrials * 1000}ul per',
          f'{open_time}ms (averaged over {ntrials} drops).')

    df1 = df1.append({
        "open_time": open_time,
        "ndrops": ntrials,
        "measured_weight": measured_weight,
        "time": datetime.datetime.now(),
    }, ignore_index=True)

# SAVE
df1['open_time'] = df1['open_time'].astype("float")
df1['measured_weight'] = df1['measured_weight'].astype("float")
df1['ndrops'] = df1['ndrops'].astype("float")

df1["weight_perdrop"] = df1["measured_weight"] / df1["ndrops"] * 1000  # in ul
df1.to_csv(sph.CALIBRATION_FUNCTION_FILE_PATH)

# FIT EXTRAPOLATION FUNCTION
time2vol = sp.interpolate.pchip(
    df1["open_time"], df1["weight_perdrop"])  # for later
vol2time = sp.interpolate.pchip(
    df1["open_time"], df1["weight_perdrop"])  # for later

xp = np.linspace(0, df1["open_time"].max(), ntrials)
ax[0].plot(xp, time2vol(xp), '-k')

# CALIBRATION CURVE
sns.scatterplot(x="open_time", y="weight_perdrop", data=df1, ax=ax[0])
ax[0].set(xlabel="Open time (ms)",
          ylabel="Measured volume (ul per drop)", title="Calibration curve")
title = f.suptitle(f"Water calibration {now}")
f.savefig(sph.CALIBRATION_CURVE_FILE_PATH)

# # =============================================================================
# # ASK THE USER FOR A LINEAR RANGE
# # =============================================================================

# messagebox.showinfo("Information", "Calibration curve completed! We're not done yet. \n \
#     Please look at the figure and indicate a min-max range over which the curve is monotonic. \n \
#     The range of drop volumes should ideally be 1.5-3uL.\n\n \
#     Close the plot before entering the range.")
# plt.show()

# min_open_time = numinput(
#     "Input", "What's the LOWEST opening time (in ms) of the linear (monotonic) range?")

# max_open_time = numinput(
#     "Input", "What's the HIGHEST opening time (in ms) of the linear (monotonic) range?")

# ax[0].axvline(min_open_time, color='black')
# ax[0].axvline(max_open_time, color='black')

# plt.show()
# f.savefig(sph.CALIBRATION_CURVE_FILE_PATH)

# # SAVE THE RANGE TOGETHER WITH THE CALIBRATION CURVE - SEPARATE FILE
# df2 = pd.DataFrame.from_dict(
#     {'min_open_time': min_open_time, 'max_open_time': max_open_time, 'index': [0]})
# df2.to_csv(sph.CALIBRATION_RANGE_FILE_PATH)
# bpod.close()
print(f'Completed water calibration {now}')
