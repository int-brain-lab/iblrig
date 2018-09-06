# !/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Example adapted from Josh Sanders' original version on Sanworks Bpod repository
"""
from pybpodapi.protocol import Bpod, StateMachine



my_bpod = Bpod()
for i in range(10):  # Main loop

	sma = StateMachine(my_bpod)

	# Set global timer 1 for 3 seconds
	sma.set_global_timer_legacy(timer_id=1, timer_duration=3)

	sma.add_state(
		state_name='ttl',  # Trigger global timer
		state_timer=1.,
		state_change_conditions={Bpod.Events.Tup: 'delay'},
		output_actions=[(Bpod.OutputChannels.BNC1, 255)])

	sma.add_state(
		state_name='delay',  # Infinite loop (with next state). Only a global timer can save us.
		state_timer=5.,
		state_change_conditions={Bpod.Events.Tup: 'exit'},
		output_actions=[])

	my_bpod.send_state_machine(sma)

	my_bpod.run_state_machine(sma)

	print("Current trial info: {0}".format(my_bpod.session.current_trial) )
my_bpod.close()