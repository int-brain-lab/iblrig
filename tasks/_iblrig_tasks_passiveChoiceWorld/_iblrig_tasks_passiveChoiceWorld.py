#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
import logging

import matplotlib.pyplot as plt
from pybpod_rotaryencoder_module.module import RotaryEncoder
from pybpodapi.protocol import Bpod, StateMachine

import online_plots as op
import task_settings
import user_settings
from session_params import SessionParamHandler
from trial_params import TrialParamHandler

log = logging.getLogger('iblrig')
log.setLevel(logging.INFO)

global sph
sph = SessionParamHandler(task_settings, user_settings)

# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()

# Rotary Encoder State Machine handler
rotary_encoder = [x for x in bpod.modules if x.name == 'RotaryEncoder1'][0]
sound_card = [x for x in bpod.modules if x.name == 'SoundCard1'][0]
# ROTARY ENCODER SEVENTS
# Set RE position to zero 'Z' + eneable all RE thresholds 'E'
# re_reset = rotary_encoder.create_resetpositions_trigger()
re_reset = 1
bpod.load_serial_message(rotary_encoder, re_reset,
                         [RotaryEncoder.COM_SETZEROPOS,  # ord('Z')
                          RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS])  # ord('E')
# Stop the stim
re_stop_stim = re_reset + 1
bpod.load_serial_message(rotary_encoder, re_stop_stim, [ord('#'), 1])
# Show the stim
re_show_stim = re_reset + 2
bpod.load_serial_message(rotary_encoder, re_show_stim, [ord('#'), 2])
# Close loop
re_close_loop = re_reset + 3
bpod.load_serial_message(rotary_encoder, re_close_loop, [ord('#'), 3])
# Play tone
sc_play_tone = re_reset + 4
bpod.load_serial_message(sound_card, sc_play_tone, [ord('P'), sph.GO_TONE_IDX])
# Play noise
sc_play_noise = re_reset + 5
bpod.load_serial_message(sound_card, sc_play_noise, [
                         ord('P'), sph.WHITE_NOISE_IDX])
# Start spontaneous activity
re_spontaneous_start = re_reset + 6
bpod.load_serial_message(sound_card, re_spontaneous_start, [ord('P'), 4])
# Start spontaneous activity
re_rfm_start = re_reset + 7
bpod.load_serial_message(sound_card, re_rfm_start, [ord('P'), 5])
# Start spontaneous activity
re_replay_start = re_reset + 8
bpod.load_serial_message(sound_card, re_replay_start, [ord('P'), 6])
# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
log.debug('Call tph creation')
tph = TrialParamHandler(sph)
log.debug('TPH CREATED!')

"""
Pre state machine?:
Launch visual stim workflow
RE command to start 5 min of spontaneous activity (sync square every x min to FPGA and Bpod?)
RE command to start 5 min of RFMapping
RE command to start 5 min of replay task stim
Trial structure:
'state_name': 'stim0_delay',
'state_timer': stim0.delay,
'output_actions': [()],
'state_change_conditions': {'Tup': 'stim0'},

'state_name': 'stim0',
'state_timer': None,
'output_actions': [(),()]
'state_change_conditions': {'Tup': 'stim1_delay'},

... repeat 5 times

Valve example:
sma.add_state(
    state_name='stim0',
    state_timer=tph.reward_valve_time,
    output_actions=[('Valve1, 255)],
    state_change_conditions={'Tup': 'stim1_delay'}
)

Tone example:
sma.add_state(
    state_name='stim0',
    state_timer=None,  # add length of tone (0.100s) + 1ms?
    output_actions=[('Serial3', sc_play_tone)],
    state_change_conditions = {
            'Tup': 'stim1_delay',
            'BNC2Low': 'stim1_delay'  # End of tone
        }
)

Noise example:
sma.add_state(
    state_name='stim0',
    state_timer=None,  # add length of noise (0.100s) + 1ms?
    output_actions=[('Serial3', sc_play_noise)],
    state_change_conditions = {
            'Tup': 'stim1_delay',
            'BNC2High': 'stim1_delay'
        }
)

Stim example:
sma.add_state(
    state_name='stim0',
    state_timer=None,  # add length of stim (0.300s) + 100ms?
    output_actions=[('Serial1', re_show_stim)],
    state_change_conditions = {
            'Tup': 'stim1_delay',
            'BNC1Low': 'stim1_delay'  # end of stim
        }
)
"""
# TODO: make tph / sph loader of file
# TODO: make files...
log.debug('start SM definition')
for i in range(sph.NTRIALS):  # Main loop
    tph.next_trial()
    log.info(f'Starting trial: {i + 1}')
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)
    if i == 0:
        sma.add_state(
            state_name='spontaneous_activity',
            state_timer=350,  # 5 minutes
            output_actions=[('BNC1', 255),  # To FPGA
                            ('Serial1', re_spontaneous_start)],
            state_change_conditions={'Tup': 'rf_mapping',
                                     'BNC1High': 'rf_mapping'}
        )

        sma.add_state(
            state_name='rf_mapping',
            state_timer=410,  # rf workflow should be 5 min
            output_actions=[('Serial1', re_rfm_start)],
            state_change_conditions={'Tup': 'replay_stims_start'}
        )

        sma.add_state(
            state_name='replay_stims_start',
            state_timer=0,
            output_actions=[('Serial1', re_replay_start)],
            state_change_conditions={'Tup': 'stim0_delay'}
        )
    else:
        sma.add_state(
            state_name='spontaneous_activity',
            state_timer=0,
            output_actions=[],
            state_change_conditions={'Tup': 'rf_mapping'}
        )

        sma.add_state(
            state_name='rf_mapping',
            state_timer=0,
            output_actions=[],
            state_change_conditions={'Tup': 'replay_stims_start'}
        )

        sma.add_state(
            state_name='replay_stims_start',
            state_timer=0,
            output_actions=[],
            state_change_conditions={'Tup': 'stim0_delay'}
        )
    # =========================================================================
    #     Start stims
    # =========================================================================
    sma.add_state(
        state_name='stim0_delay',
        state_timer=tph.stim_delay[i, 0],
        output_actions=[],
        state_change_conditions={'Tup': 'stim0'}
    )

    sma.add_state(
        state_name='stim0',
        state_timer=0,
        output_actions=[],
        state_change_conditions={'Tup': 'stim1_delay'}
    )

    sma.add_state(
        state_name='stim1_delay',
        state_timer=tph.stim_delay[i, 1],
        output_actions=[],
        state_change_conditions={'Tup': 'stim1'}
    )

    sma.add_state(
        state_name='stim1',
        state_timer=0,
        output_actions=[],
        state_change_conditions={'Tup': 'stim2_delay'}
    )

    sma.add_state(
        state_name='stim2_delay',
        state_timer=tph.stim_delay[i, 2],
        output_actions=[],
        state_change_conditions={'Tup': 'stim2'}
    )

    sma.add_state(
        state_name='stim2',
        state_timer=0,
        output_actions=[],
        state_change_conditions={'Tup': 'stim3_delay'}
    )

    sma.add_state(
        state_name='stim3_delay',
        state_timer=tph.stim_delay[i, 3],
        output_actions=[],
        state_change_conditions={'Tup': 'stim3'}
    )

    sma.add_state(
        state_name='stim3',
        state_timer=0,
        output_actions=[],
        state_change_conditions={'Tup': 'stim4_delay'}
    )

    sma.add_state(
        state_name='stim4_delay',
        state_timer=tph.stim_delay[i, 4],
        output_actions=[],
        state_change_conditions={'Tup': 'stim4'}
    )

    sma.add_state(
        state_name='stim4',
        state_timer=0,
        output_actions=[],
        state_change_conditions={'Tup': 'exit'}
    )

    bpod.send_state_machine(sma)
    # Run state machine
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
    tph = tph.trial_completed(bpod.session.current_trial.export())

    as_data = tph.save_ambient_sensor_data(bpod, sph.SESSION_RAW_DATA_FOLDER)

bpod.close()


if __name__ == '__main__':
    print('main')
