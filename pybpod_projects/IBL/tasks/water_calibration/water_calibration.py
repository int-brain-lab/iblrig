# !/usr/bin/python3
# -*- coding: utf-8 -*-

# automatic water calibration for pyBpod
# Anne Urai, CSHL, 2018

from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule

# for dialog box
import tkinter as tk

# ask Nicco if I need to separately import these?
import serial, time, re, datetime, os, glob # https://pyserial.readthedocs.io/en/latest/shortintro.html
import seaborn as sns # for easier plotting at the end
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import scipy as sp

# SETTINGS SPECIFIED BY THE USER
bpod  			 = Bpod()
COMport_string   = 'COM7' # leave NaN for manual weight logging
calibration_path = "C:\\ibldata\\calibrations_water" # TODO: softcode?

# OUTPUT OVERVIEW FIGURE
sns.set()
sns.set_context(context="talk")
f, ax = plt.subplots(1,2, sharex=False, figsize=(15, 7))

# TIME OF STARTING THE CALIBRATION
now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
print(now)

# =============================================================================
# OPEN THE VALVE FOR A SPECIFIED AMOUNT OF TIME
# =============================================================================

def water_drop(open_time, ntrials=100, iti=1, bpod=bpod):

	# Start state machine definition
	for i in range(ntrials):

		sma = StateMachine(bpod)

	    # open and close valve
		sma.add_state(
			state_name='reward',
	    	state_timer=open_time,
	    	state_change_conditions={'Tup': 'iti'},
	    	output_actions=[('Valve1', 1)])

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

def scale_read(COMPORT_string=COMport_string):

	if not COMport_string:
		# ask the user to manually input
		grams = float(raw_input("Enter scale read: "))
		
	else:
		# http://dmx.ohaus.com/WorkArea/downloadasset.aspx?id=3600
	    # https://github.com/glansberry/ohaus_scale_data/blob/master/scale.py
		ser = serial.Serial(COMPORT_string, baudrate=9600, timeout=3)  # open serial port

		# grab the software version and initialize
		ser.write(b'V\r\n') 
		time.sleep(0.5)
		version = ser.readline()

		# READ THE CURRENT WEIGHT
		ser.write(b'IP\r\n') # ping the scale to print
		time.sleep(0.5)
		grams = ser.readline()

		# extract number 
		grams = grams.decode("utf-8")
		grams = grams.strip("gN ")
		grams = re.findall(r"[-+]?\d*\.\d+|\d+",grams)
		grams = float(grams[0])
		# print('Reading Ohaus %s %fg' %(version.decode("utf-8"), grams))

	return grams

# =============================================================================
# FIRST, GENERATE A CALIBRATION CURVE - OPEN TIMES VS DROP SIZE
# see https://github.com/cortex-lab/Rigbox/blob/5d926cdafdfcb54cd74c77e152d158d3d837a90c/%2Bhw/calibrate.m
# and https://github.com/sanworks/Bpod_Gen2/blob/14b78143e071c1cfda391b1754dba928ccc27792/Functions/Calibration/Liquid%20Reward/BpodLiquidCalibration.m
# bpod wiki https://sites.google.com/site/bpoddocumentation/bpod-user-guide/liquid-calibration
# =============================================================================

# initialize a dataframe with the results
df1 		= pd.DataFrame(columns=["time", "open_time", "ndrops", "measured_weight"])
ntrials 	= 100
open_times  = range(10, 100, 3) # in milliseconds, 10 to 100ms opening time

for open_time in open_times:

	try:
		time.sleep(1)
		startweight = scale_read(COMport_string)
		water_drop(open_time/1000, ntrials=ntrials, iti=0.2, bpod=bpod) # deliver ntrials drops of water
		time.sleep(1)
		measured_weight = scale_read(COMport_string) - startweight
		# summarize
		print('Weight change = %.2fg: delivered %ful per %fms (averaged over %d drops).' 
			%(measured_weight, measured_weight / ntrials * 1000, open_time, ntrials)); 

		df1 = df1.append({
			"open_time": 			open_time,
			"ndrops":  			ntrials,
			"measured_weight": 	measured_weight,
			"time": 				datetime.datetime.now(),
			}, ignore_index=True)
	except:
		pass

# SAVE
df1['open_time'] 		= df1['open_time'].astype("float")
df1['measured_weight'] 	= df1['measured_weight'].astype("float")
df1['ndrops'] 			= df1['ndrops'].astype("float")

df1["weight_perdrop"] = df1["measured_weight"] / df1["ndrops"] * 1000 # in ul
df1.to_csv(os.path.join(calibration_path, "%s_calibration_function.csv" %now))

# FIT EXTRAPOLATION FUNCTION
time2vol 	= sp.interpolate.pchip(df1["open_time"], df1["weight_perdrop"]) # for later
vol2time 	= sp.interpolate.pchip(df1["open_time"], df1["weight_perdrop"]) # for later

xp 		= np.linspace(0, df1["open_time"].max(), 100)
ax[0].plot(xp, time2vol(xp), '-k')

# CALIBRATION CURVE
sns.scatterplot(x="open_time", y="weight_perdrop", data=df1, ax=ax[0])
ax[0].set(xlabel="Open time (ms)", ylabel="Measured volume (ul per drop)", title="Calibration curve")
title = f.suptitle("Water calibration %s" %now)
plt.show()
f.savefig(os.path.join(calibration_path, '%s_curve.pdf' %now))

# =============================================================================
# ASK THE USER FOR A LINEAR RANGE
# =============================================================================

tk.messagebox.showinfo("Information", "Calibration curve completed! We're not done yet - \
	please look at the figure and indicate a min-max range over which the curve is monotonic. \
	The range of drop volumes should ideally be 1.5-3uL.")

min_open_time = simpledialog.askinteger("Input", "What's the LOWEST opening time (in ms) of the linear (monotonic) range?",
                                 parent=application_window,
                                 minvalue=open_times.min(), maxvalue=open_times.max())

max_open_time = simpledialog.askinteger("Input", "What's the HIGHEST opening time (in ms) of the linear (monotonic) range?",
                                 parent=application_window,
                                 minvalue=open_times.min(), maxvalue=open_times.max())

ax[0].axhline(x=min_open_time, color='black')
ax[0].axhline(x=max_open_time, color='black')

plt.show()
f.savefig(os.path.join(calibration_path, '%s_curve.pdf' %now))

# SAVE THE RANGE TOGETHER WITH THE CALIBRATION CURVE - SEPARATE FILE
df2 = pd.DataFrame.from_dict({'min_open_time': min_open_time, 'max_open_time': max_open_time})
df2.to_csv(os.path.join(calibration_path, "%s_calibration_range.csv" %now))

print('Completed water calibration %s' %now)
bpod.close()
