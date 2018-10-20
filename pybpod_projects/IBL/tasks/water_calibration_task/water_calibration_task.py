# !/usr/bin/python3
# -*- coding: utf-8 -*-

"""
A protocol to calibrate the water system. In addition, to contro the lights.
"""

from user_settings import *
from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
import timeit

# Exacution time
start = 0
START_APP = timeit.default_timer()


"""
VAR_0 contains the number of cycles
VAR_1 contains the interval between one trial and the next one
VAR_2 contains the port to use. 
VAR_3 contains the timer of valves
"""

portsToOpen = [int(port) for port in VAR_2.split('-')]
nPorts = len(portsToOpen)
timerValve  = [float(t) for t in VAR_3.split('-')]

# ----> Start the task
my_bpod = Bpod()
for i in range(int(VAR_0)):  # Main loop
    print('Trial: ', i + 1)

    sma = StateMachine(my_bpod)
    changeTostate = ''
    counter = nPorts

    for p in range(nPorts):
        counter -= 1
        if counter > 0:
            changeTostate = 'GetWater_P' + str(portsToOpen[p+1])
        else:
            changeTostate = 'End'

        sma.add_state(
            state_name  ='GetWater_P' + str(portsToOpen[p]),
            state_timer = timerValve[p],
            state_change_conditions = {EventName.Tup: changeTostate},
            output_actions = [(OutputChannel.Valve, portsToOpen[p]), (OutputChannel.LED, portsToOpen[p])])

    sma.add_state(
        state_name = 'End',
        state_timer = float(VAR_1),
        state_change_conditions={EventName.Tup: 'exit'},
        output_actions=[])

    my_bpod.send_state_machine(sma)  # Send state machine description to Bpod device
    my_bpod.run_state_machine(sma)  # Run state machine

my_bpod.close()
print('EXECUTION TIME: ', timeit.default_timer() - START_APP)







