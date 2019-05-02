#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
from pybpodapi.protocol import Bpod, StateMachine
from pybpod_rotaryencoder_module.module import RotaryEncoder
import logging

from session_params import SessionParamHandler
from trial_params import TrialParamHandler
import task_settings
import user_settings

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

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
tph = TrialParamHandler(sph)

for i in range(sph.NTRIALS):  # Main loop
    tph.next_trial()
    log.info(f'Starting trial: {i + 1}')
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)

    if i == 0:  # First trial exception start camera
        sma.add_state(
            state_name='trial_start',
            state_timer=0,  # ~100µs hardware irreducible delay
            state_change_conditions={'Tup': 'stim_on'},
            output_actions=[('Serial1', re_stop_stim),
                            ('SoftCode', 3)])  # sart camera
    else:
        sma.add_state(
            state_name='trial_start',
            state_timer=1,  # Stim off for 1 sec
            state_change_conditions={'Tup': 'stim_on'},
            output_actions=[('Serial1', re_stop_stim)])

    sma.add_state(
        state_name='stim_on',
        state_timer=tph.delay_to_stim_center,
        state_change_conditions={'Tup': 'stim_center'},
        output_actions=[('Serial1', re_show_stim), tph.out_tone])

    sma.add_state(
        state_name='stim_center',
        state_timer=0.5,
        state_change_conditions={'Tup': 'reward'},
        output_actions=[('Serial1', re_show_center)])

    sma.add_state(
        state_name='reward',
        state_timer=tph.reward_valve_time,
        state_change_conditions={'Tup': 'iti'},
        output_actions=[('Valve1', 255)])

    sma.add_state(
        state_name='iti',
        state_timer=tph.iti,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[])

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached

    trial_data = tph.trial_completed(bpod.session.current_trial.export())
    tevents = trial_data['behavior_data']['Events timestamps']

    ev_bnc1 = sph.get_port_events(tevents, name='BNC1')
    ev_bnc2 = sph.get_port_events(tevents, name='BNC2')
    ev_port1 = sph.get_port_events(tevents, name='Port1')

    NOT_SAVED = 'not saved - deactivated in task settings'
    NOT_FOUND = 'COULD NOT FIND DATA ON {}'

    as_msg = NOT_SAVED
    bnc1_msg = NOT_FOUND.format('BNC1') if not ev_bnc1 else 'OK'
    bnc2_msg = NOT_FOUND.format('BNC2') if not ev_bnc2 else 'OK'
    port1_msg = NOT_FOUND.format('Port1') if not ev_port1 else 'OK'

    if sph.RECORD_AMBIENT_SENSOR_DATA:
        data = sph.save_ambient_sensor_reading(bpod)
        as_msg = 'saved'

    msg = f"""
##########################################
TRIAL NUM:              {trial_data['trial_num']}
DELAY TO WATER WAS:     {trial_data['delay_to_stim_center']}
WATER DELIVERED:        {trial_data['water_delivered']}
TIME FROM START:        {trial_data['elapsed_time']}
AMBIENT SENSOR DATA:    {as_msg}
##########################################"""
    log.info(msg)

    warn_msg = f"""
        ##########################################
                NOT FOUND: SYNC PULSES
        ##########################################
        VISUAL STIMULUS SYNC:   {bnc1_msg}
        SOUND SYNC:             {bnc2_msg}
        CAMERA SYNC:            {port1_msg}
        ##########################################"""
    if not ev_bnc1 or not ev_bnc2 or not ev_port1:
        log.warning(warn_msg)

bpod.close()


if __name__ == '__main__':
    print('main')
