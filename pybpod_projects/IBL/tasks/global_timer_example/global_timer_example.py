# !/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Example adapted from Josh Sanders' original version on Sanworks Bpod repository
"""
from pybpodapi.protocol import Bpod, StateMachine



my_bpod = Bpod()

sma = StateMachine(my_bpod)

# Set global timer 1 for 3 seconds
sma.set_global_timer_legacy(timer_id=1, timer_duration=3)

sma.add_state(
	state_name='TimerTrig',  # Trigger global timer
	state_timer=0,
	state_change_conditions={Bpod.Events.Tup: 'Port1Lit'},
	output_actions=[(Bpod.OutputChannels.GlobalTimerTrig, 1)])

sma.add_state(
	state_name='Port1Lit',  # Infinite loop (with next state). Only a global timer can save us.
	state_timer=.25,
	state_change_conditions={Bpod.Events.Tup: 'Port3Lit', Bpod.Events.GlobalTimer1_End: 'exit'},
	output_actions=[('Valve', 2)])

sma.add_state(
	state_name='Port3Lit',
	state_timer=.25,
	state_change_conditions={Bpod.Events.Tup: 'Port1Lit', Bpod.Events.GlobalTimer1_End: 'exit'},
	output_actions=[(Bpod.OutputChannels.PWM3, 255)])

my_bpod.send_state_machine(sma)

my_bpod.run_state_machine(sma)

print("Current trial info: {0}".format(my_bpod.session.current_trial) )

my_bpod.close()