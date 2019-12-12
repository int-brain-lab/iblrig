#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 4th 2019, 11:52:41 am
import logging
import sys

import ibllib.io.raw_data_loaders as raw
from pybpodapi.protocol import Bpod, StateMachine

import iblrig.bonsai as bonsai
import iblrig.frame2TTL
import iblrig.params as params

sys.stdout.flush()

log = logging.getLogger('iblrig')
log.setLevel(logging.INFO)

PARAMS = params.load_params()


def softcode_handler(data):
    if data:
        # Launch the workflow
        bonsai.start_frame2ttl_test()
    return


# Set the thresholds for Frame2TTL
iblrig.frame2TTL.get_and_set_thresholds()
# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()
# Soft code handler function can run arbitrary code from within state machine
bpod.softcode_handler_function = softcode_handler
log.info(f'Starting 1000 sync square pulses')
sys.stdout.flush()
# =============================================================================
#     Start state machine definition
# =============================================================================
sma = StateMachine(bpod)
sma.add_state(
    state_name='start',
    state_timer=2,
    output_actions=[('SoftCode', 1)],
    state_change_conditions={'Tup': 'listen'}
)
sma.add_state(
    state_name='listen',
    state_timer=25,
    output_actions=[],
    state_change_conditions={'Tup': 'exit'}
)
# Send state machine description to Bpod device
bpod.send_state_machine(sma)
# Run state machine
bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached

data = bpod.session.current_trial.export()

BNC1 = raw.get_port_events(data['Events timestamps'], name='BNC1')
# print(BNC1, flush=True)
# print(BNC1, flush=True)
# print(len(BNC1), flush=True)
if len(BNC1) == 1000:
    log.info("PASS 1000 pulses detected")
    sys.stdout.flush()
else:
    log.error("FAILED to detect 1000 pulses detected")
    sys.stdout.flush()

bpod.close()


if __name__ == '__main__':
    print('done', flush=True)
