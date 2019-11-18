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


def bpod_loop_handler():
    f.canvas.flush_events()  # 100µs


# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()

# Loop handler function is used to flush events for the online plotting
bpod.loop_handler = bpod_loop_handler
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

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
log.debug('Call tph creation')
tph = TrialParamHandler(sph)
log.debug('TPH CREATED!')

log.debug('make fig')
f, axes = op.make_fig(sph)
log.debug('pause')
plt.pause(1)
"""
Pre state machine?:
Launch visual stim workflow
OSC command to start 5 min of spontaneous activity (sync square every x min to FPGA and Bpod?)
OSC command to start 5 min of RFMapping
OSC command to start 5 min of replay task stim
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
            state_change_conditions={'Tup': 'rf_mapping'},
            output_actions=[('BNC1', 255)])  # To FPGA

        sma.add_state(
            state_name='rf_mapping',
            state_timer=700,  # rf workflow should be 5 min
            state_change_conditions={'Tup': 'quiescent_period'},
            output_actions=[('Serial1', re_reset)])

    else:
        sma.add_state(
            state_name='trial_start',
            state_timer=0,  # ~100µs hardware irreducible delay
            state_change_conditions={'Tup': 'reset_rotary_encoder'},
            output_actions=[('BNC1', 255)])  # To FPGA

    sma.add_state(
        state_name='reset_rotary_encoder',
        state_timer=0,
        state_change_conditions={'Tup': 'quiescent_period'},
        output_actions=[('Serial1', re_reset)])

    sma.add_state(  # '>back' | '>reset_timer'
        state_name='quiescent_period',
        state_timer=tph.quiescent_period,
        state_change_conditions={'Tup': 'stim_on',
                                 tph.movement_left: 'reset_rotary_encoder',
                                 tph.movement_right: 'reset_rotary_encoder'},
        output_actions=[])

    sma.add_state(
        state_name='stim_on',
        state_timer=0.1,
        state_change_conditions={
            'Tup': 'interactive_delay',
            'BNC1High': 'interactive_delay',
            'BNC1Low': 'interactive_delay'
        },
        output_actions=[('Serial1', re_show_stim)])

    sma.add_state(
        state_name='interactive_delay',
        state_timer=tph.interactive_delay,
        state_change_conditions={'Tup': 'play_tone'},
        output_actions=[])

    sma.add_state(
        state_name='play_tone',
        state_timer=0.001,
        state_change_conditions={
            'Tup': 'reset2_rotary_encoder',
            'BNC2High': 'reset2_rotary_encoder'
        },
        output_actions=[('Serial3', sc_play_tone)])

    sma.add_state(
        state_name='reset2_rotary_encoder',
        state_timer=0,
        state_change_conditions={'Tup': 'closed_loop'},
        output_actions=[('Serial1', re_reset)])

    sma.add_state(
        state_name='closed_loop',
        state_timer=tph.response_window,
        state_change_conditions={'Tup': 'no_go',
                                 tph.event_error: 'error',
                                 tph.event_reward: 'reward'},
        output_actions=[('Serial1', re_close_loop)])

    sma.add_state(
        state_name='no_go',
        state_timer=tph.iti_error,
        state_change_conditions={'Tup': 'exit_state'},
        output_actions=[('Serial1', re_stop_stim),
                        ('Serial3', sc_play_noise)])

    sma.add_state(
        state_name='error',
        state_timer=tph.iti_error,
        state_change_conditions={'Tup': 'exit_state'},
        output_actions=[('Serial3', sc_play_noise)])

    sma.add_state(
        state_name='reward',
        state_timer=tph.reward_valve_time,
        state_change_conditions={'Tup': 'correct'},
        output_actions=[('Valve1', 255),
                        ('BNC1', 255)])  # To FPGA

    sma.add_state(
        state_name='correct',
        state_timer=tph.iti_correct,
        state_change_conditions={'Tup': 'exit_state'},
        output_actions=[])

    sma.add_state(
        state_name='exit_state',
        state_timer=0.5,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[('BNC1', 255),
                        ('Serial1', re_stop_stim),
                        ])

    # if i == 0:
    #     sph.warn_ephys()
    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
    tph = tph.trial_completed(bpod.session.current_trial.export())

    as_data = tph.save_ambient_sensor_data(bpod, sph.SESSION_RAW_DATA_FOLDER)
    tph.show_trial_log()

    # Update online plots
    op.update_fig(f, axes, tph)

    tph.check_sync_pulses()
    stop_crit = tph.check_stop_criterions()
    if stop_crit and sph.USE_AUTOMATIC_STOPPING_CRITERIONS:
        if stop_crit == 1:
            msg = "STOPPING CRITERIA Nº1: PLEASE STOP TASK AND REMOVE MOUSE\
            \n < 400 trials in 45min"
            f.patch.set_facecolor('xkcd:mint green')
        elif stop_crit == 2:
            msg = "STOPPING CRITERIA Nº2: PLEASE STOP TASK AND REMOVE MOUSE\
            \nMouse seems to be inactive"
            f.patch.set_facecolor('xkcd:yellow')
        elif stop_crit == 3:
            msg = "STOPPING CRITERIA Nº3: PLEASE STOP TASK AND REMOVE MOUSE\
            \n> 90 minutes have passed since session start"
            f.patch.set_facecolor('xkcd:red')

        if not sph.SUBJECT_DISENGAGED_TRIGGERED and stop_crit:
            patch = {'SUBJECT_DISENGAGED_TRIGGERED': stop_crit,
                     'SUBJECT_DISENGAGED_TRIALNUM': i + 1}
            sph.patch_settings_file(patch)
        [log.warning(msg) for x in range(5)]

bpod.close()


if __name__ == '__main__':
    print('main')
