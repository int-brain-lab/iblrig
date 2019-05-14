#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 4th 2019, 11:52:41 am
from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine

ntrials = 1
valve_on_time = 3600
iti = 0.9

# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================

for i in range(ntrials):
    print('Starting trial: ', i + 1)
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)
    sma.add_state(
        state_name='init',
        state_timer=0,
        state_change_conditions={'Tup': 'reward'},
        output_actions=[])

    sma.add_state(
        state_name='reward',
        state_timer=valve_on_time,
        state_change_conditions={'Tup': 'iti'},
        output_actions=[('Valve1', 255)])

    sma.add_state(
        state_name='iti',
        state_timer=iti,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[])

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)

    # Run state machine
    bpod.run_state_machine(sma)

    print("Current trial info: {0}".format(bpod.session.current_trial))

bpod.close()

if __name__ == '__main__':
    print('main')
