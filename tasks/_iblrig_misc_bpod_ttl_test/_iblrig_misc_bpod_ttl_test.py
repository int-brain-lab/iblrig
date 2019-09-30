#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
import logging

import numpy as np
from pybpod_rotaryencoder_module.module import RotaryEncoder
from pybpodapi.protocol import Bpod, StateMachine

import task_settings
import user_settings
from session_params import SessionParamHandler
from trial_params import TrialParamHandler

log = logging.getLogger('iblrig')
log.setLevel(logging.INFO)

global sph
sph = SessionParamHandler(task_settings, user_settings)


def softcode_handler(data):
    """
    Soft codes should work with resasonable latency considering our limiting
    factor is the refresh rate of the screen which should be 16.667ms @ a frame
    rate of 60Hz
    1 : go_tone
    2 : white_noise
    """
    global sph
    if data == 0:
        sph.stop_sound()
    elif data == 1:
        sph.play_tone()
    elif data == 3:
        sph.start_camera_recording()


# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()
# Soft code handler function can run arbitrary code from within state machine
bpod.softcode_handler_function = softcode_handler
# Rotary Encoder State Machine handle
rotary_encoder = [x for x in bpod.modules if x.name == 'RotaryEncoder1'][0]
# ROTARY ENCODER EVENTS
rotary_encoder_reset = 1
bpod.load_serial_message(rotary_encoder, rotary_encoder_reset,
                         [RotaryEncoder.COM_SETZEROPOS,  # ord('Z')
                          RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS])  # ord('E')
# Stop the stim
re_stop_stim = rotary_encoder_reset + 1
bpod.load_serial_message(rotary_encoder, re_stop_stim, [ord('#'), 1])
# Show the stim
re_show_stim = rotary_encoder_reset + 2
bpod.load_serial_message(rotary_encoder, re_show_stim, [ord('#'), 2])
# Shwo stim at center of screen
re_show_center = rotary_encoder_reset + 3
bpod.load_serial_message(rotary_encoder, re_show_center, [ord('#'), 3])
if sph.SOFT_SOUND is None:
    # SOUND CARD
    sound_card = [x for x in bpod.modules if x.name == 'SoundCard1'][0]
    # Play tone
    sc_play_tone = rotary_encoder_reset + 4
    bpod.load_serial_message(sound_card, sc_play_tone, [
                             ord('P'), sph.GO_TONE_IDX])

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
tph = TrialParamHandler(sph)

bad_stim_count = 0
bad_tone_count = 0

for i in range(sph.NTRIALS):  # Main loop
    tph.next_trial()
    log.info(f'Starting trial: {i + 1}')
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)

    if i == 0:
        sma.add_state(
            state_name='stim_on',
            state_timer=10,
            state_change_conditions={'Tup': 'bad_stim',
                                     'BNC1High': 'stim_off',
                                     'BNC1Low': 'stim_off'},
            output_actions=[('Serial1', re_show_stim)])
    else:
        sma.add_state(
            state_name='stim_on',
            state_timer=1,
            state_change_conditions={'Tup': 'bad_stim',
                                     'BNC1High': 'stim_off',
                                     'BNC1Low': 'stim_off'},
            output_actions=[('Serial1', re_show_stim)])

    sma.add_state(
        state_name='stim_off',
        state_timer=1,  # Stim off for 1 sec
        state_change_conditions={'Tup': 'bad_stim',
                                 'BNC1High': 'play_tone',
                                 'BNC1Low': 'play_tone'},
        output_actions=[('Serial1', re_stop_stim)])

    sma.add_state(
        state_name='bad_stim',
        state_timer=0,
        state_change_conditions={'Tup': 'play_tone'},
        output_actions=[])

    sma.add_state(
        state_name='play_tone',
        state_timer=1,
        state_change_conditions={'Tup': 'bad_tone',
                                 'BNC2High': 'exit',
                                 'BNC2Low': 'exit'},
        output_actions=[tph.out_tone])

    sma.add_state(
        state_name='bad_tone',
        state_timer=0,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[])

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached

    trial_data = tph.trial_completed(bpod.session.current_trial.export())

    bad_tone_state = trial_data['behavior_data']['States timestamps']['bad_tone']
    bad_stim_state = trial_data['behavior_data']['States timestamps']['bad_stim']
    if not np.all(np.isnan(bad_stim_state)):
        bad_stim_count += 1
        log.warning(f'Missing stims: {bad_stim_count}')
    if not np.all(np.isnan(bad_tone_state)):
        bad_tone_count += 1
        log.warning(f'Missing tones: {bad_tone_count}')

sph.check_data()
bpod.close()


if __name__ == '__main__':
    print('main')
