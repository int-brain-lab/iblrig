# !/usr/bin/python3
# -*- coding: utf-8 -*-

# automatic water calibration for pyBpod
# Anne Urai, CSHL, 2018

from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule

# ask Nicco if I need to separately import these?
import serial, time, re, datetime, os, glob # https://pyserial.readthedocs.io/en/latest/shortintro.html
import seaborn as sns # for easier plotting at the end
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import scipy as sp

# SETTINGS SPECIFIED BY THE USER
bpod  			 = Bpod()
COMport_string   = 'COM7'
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
f.savefig(os.path.join(calibration_path, '%s_curve.pdf' %now))

# =============================================================================
# SECOND, TEST THE PRECISION OF ESTIMATED VS MEASURED DROP SIZE
# =============================================================================

# # some settings
# target_drop_sizes = np.linspace(1.5, 3, 15) # in ul
# precision_perdrop = 0.1 # ul - the precision should be at most the step size between drop sizes
# precision 		  = precision_perdrop  * ntrials / 1000

# # files 			  = glob.glob(os.path.join(calibration_path, "/*.csv"))
# # if not a:
# # 	bestguess 	  = 0.02 # starting point for seconds to open for 1ul of water
# # else:
# # 	files.sort(reverse=True) # sort by date
# # 	previouscalibration = df.read_csv(os.path.join(calibration_path, files[0]))
# # 	previouscalibration['open_time'].mean()
# # 	bestguess = previouscalibration.loc[previouscalibration['calibrated'] == True, 'open_time'] /
# # 		previouscalibration.loc[previouscalibration['calibrated'] == True, 'target_drop_size']
# # 	bestguess = bestguess.mean()

# # initialize a dataframe with the results
# df = pd.DataFrame(columns=["time", "target_drop_size", "ndrops", "target_weight", 
# "open_time", "measured_weight", "precision", "calibrated", "attempt"])

# # =============================================================================
# # LET'S GO
# # =============================================================================

# for drop_size in target_drop_sizes:

# 	# 1. specify the expected total weight for this drop size
# 	target_weight 	= drop_size * ntrials / 1000 # in grams
# 	calibrated 		= False

# 	# GRAB OPEN_TIME FROM THE CALIBRATION CURVE
# 	open_time 		= vol2time(drop_size)
# 	assert(open_time > 0)
# 	print(open_time)

# 	# 2. drop some water and measure
# 	for attempts in range(20):

# 		# tare the scale before starting
# 		try: # if there was a previous attempt, grab the last one's final weight as the new starting point
# 			startweight = newweight
# 		except:
# 			startweight = scale_read(COMport_string)

# 		# HOW LONG WILL THIS TAKE?
# 		eta = open_time * ntrials + 0.5*ntrials
# 		print("Calibrating for a drop size of %dul will take approximately %d seconds \n" %(drop_size, eta))

# 		# 2a. deliver ntrials drops of water
# 		water_drop(open_time, ntrials=ntrials, iti=0.5, bpod=bpod)

# 		# 2b. how much does this weigh?
# 		newweight = scale_read(COMport_string)
# 		measured_weight = newweight - startweight

# 		# 2c. is this sufficiently close to what we expected?
# 		if (measured_weight < target_weight+precision) & (measured_weight > target_weight-precision):
# 			calibrated = True

# 		# 2d. save to a dataframe
# 		df = df.append({
# 		     "target_drop_size": 	drop_size,
# 		     "ndrops":  			ntrials,
# 		     "target_weight": 		target_weight,
# 		     "open_time": 			open_time,
# 		     "measured_weight": 	measured_weight,
# 		     "precision": 			precision,
# 		     "calibrated": 			calibrated,
# 		     "attempt": 			attempts,
# 		     "time": 				datetime.datetime.now(),
# 		      }, ignore_index=True)

# 		# 2e. do we need to continue?
# 		if calibrated:
# 			bestguess = open_time / drop_size
# 			break
# 		else:
# 			# come up with a better next guess - assume linearity
# 			open_time = open_time * (target_weight/measured_weight)

# 	# check that we successfully calibrated
# 	if calibrated is False:
# 		print('Did not succeed after %d attempts. Something seems seriously wrong. \n' %(attempts))
# 	else:
# 		print('Completed water calibration')


# # set some data types
# df['target_drop_size'] 	= df['target_drop_size'].astype("float")
# df['ndrops'] 			= df['ndrops'].astype("int")
# df['target_weight'] 	= df['target_weight'].astype("float")
# df['open_time'] 		= df['open_time'].astype("float")
# df['measured_weight'] 	= df['measured_weight'].astype("float")
# df['measured_weight'] 	= df['measured_weight'].astype("float")
# df['attempt'] 			= df['attempt'].astype("int")

# # =============================================================================
# # SAVE THE RESULTS FILE	
# # =============================================================================

# df.to_csv(os.path.join(calibration_path, "%s_calibration_check.csv" %now))

# # CALIBRATION RESULTS
# ax[1].plot( [0,df.measured_weight.max()],[0,df.measured_weight.max()], color='k') # identity line
# try:
# 	sns.scatterplot(x="target_weight", y="measured_weight", 
# 		style="calibrated", hue="attempt", legend="full", markers=["s", "o"], 
# 		size="calibrated", size_order=[1,0],
# 		palette="ch:r=-.5,l=.75", data=df, ax=ax[1])
# except:
# 	sns.scatterplot(x="target_weight", y="measured_weight", 
# 		style="calibrated", legend="full", markers=["s", "o"], size_order=[1,0],
# 		data=df, ax=ax[1])
# ax[1].set(xlabel="Target weight (g)", ylabel="Measured weight (g)")
# lgd = ax[1].legend(loc='center', bbox_to_anchor=(0.4, -0.4), ncol=2) # move box outside

# plt.axis('tight')
#f.savefig(os.path.join(calibration_path, '%s.pdf' %now), bbox_extra_artists=(lgd,title), bbox_inches='tight')

# =============================================================================
# RANDOM STUFF
# =============================================================================

print('Completed water calibration')
bpod.close()
