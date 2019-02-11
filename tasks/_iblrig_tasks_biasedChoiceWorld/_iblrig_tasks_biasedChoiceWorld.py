# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-10-09 13:32:28
from pybpodapi.protocol import Bpod, StateMachine
from pybpod_rotaryencoder_module.module import RotaryEncoder
import matplotlib.pyplot as plt
import logging

from session_params import SessionParamHandler
from trial_params import TrialParamHandler
import task_settings
import user_settings
import online_plots as op

log = logging.getLogger('iblrig')
log.setLevel(logging.INFO)

global sph
sph = SessionParamHandler(task_settings, user_settings)


def bpod_loop_handler():
    f.canvas.flush_events()  # 100µs


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
    if data == 1:
        sph.play_tone()
    elif data == 2:
        sph.play_noise()
    # sph.OSC_CLIENT.send_message("/e", data)


# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()

# Loop handler function is used to flush events for the online plotting
bpod.loop_handler = bpod_loop_handler
# Soft code handler function can run arbitrary code from within state machine
bpod.softcode_handler_function = softcode_handler
# Rotary Encoder State Machine handler
rotary_encoder = [x for x in bpod.modules if x.name == 'RotaryEncoder1'][0]
# ROTARY ENCODER SEVENTS
# Set RE position to zero 'Z' + eneable all RE thresholds 'E'
# rotary_encoder_reset = rotary_encoder.create_resetpositions_trigger()
rotary_encoder_reset = 1
bpod.load_serial_message(rotary_encoder, rotary_encoder_reset,
                         [RotaryEncoder.COM_SETZEROPOS,  # ord('Z')
                          RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS])  # ord('E')
# Stop the stim
rotary_encoder_e1 = rotary_encoder_reset + 1
bpod.load_serial_message(rotary_encoder, rotary_encoder_e1,
                         [ord('#'), 1])
# Show the stim
rotary_encoder_e2 = rotary_encoder_reset + 2
bpod.load_serial_message(rotary_encoder, rotary_encoder_e2,
                         [ord('#'), 2])
# Close loop
rotary_encoder_e3 = rotary_encoder_reset + 3
bpod.load_serial_message(rotary_encoder, rotary_encoder_e3,
                         [ord('#'), 3])

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
tph = TrialParamHandler(sph)

f, ax_bars, ax_psyc = op.make_fig()
psyfun_df = op.make_psyfun_df()
plt.pause(1)

sph.start_camera_recording()
for i in range(sph.NTRIALS):  # Main loop
    tph.next_trial()
    log.info(f'Starting trial: {i + 1}')
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)

    sma.add_state(
        state_name='trial_start',
        state_timer=0,  # ~100µs hardware irreducible delay
        state_change_conditions={'Tup': 'reset_rotary_encoder'},
        output_actions=[('Serial1', rotary_encoder_e1),
                        ('SoftCode', 0),
                        ])  # stop stim

    sma.add_state(
        state_name='reset_rotary_encoder',
        state_timer=0,
        state_change_conditions={'Tup': 'quiescent_period'},
        output_actions=[('Serial1', rotary_encoder_reset)])

    sma.add_state(  # '>back' | '>reset_timer'
        state_name='quiescent_period',
        state_timer=tph.quiescent_period,
        state_change_conditions={'Tup': 'stim_on',
                                 tph.movement_left: 'reset_rotary_encoder',
                                 tph.movement_right: 'reset_rotary_encoder'},
        output_actions=[])

    sma.add_state(
        state_name='stim_on',
        state_timer=tph.interactive_delay,
        state_change_conditions={'Tup': 'reset2_rotary_encoder'},
        output_actions=[('Serial1', rotary_encoder_e2)])  # show stim

    sma.add_state(
        state_name='reset2_rotary_encoder',
        state_timer=0,
        state_change_conditions={'Tup': 'closed_loop'},
        output_actions=[('Serial1', rotary_encoder_reset)])

    sma.add_state(
        state_name='closed_loop',
        state_timer=tph.response_window,
        state_change_conditions={'Tup': 'no_go',
                                 tph.event_error: 'error',
                                 tph.event_reward: 'reward'},
        output_actions=[('Serial1', rotary_encoder_e3),  # close stim loop
                        tph.out_tone])

    sma.add_state(
        state_name='no_go',
        state_timer=tph.iti_error,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[tph.out_noise])

    sma.add_state(
        state_name='error',
        state_timer=tph.iti_error,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[tph.out_noise])  # play noise

    sma.add_state(
        state_name='reward',
        state_timer=tph.reward_valve_time,
        state_change_conditions={'Tup': 'correct'},
        output_actions=[('Valve1', 255)])

    sma.add_state(
        state_name='correct',
        state_timer=tph.iti_correct,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[])

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached

    trial_data = tph.trial_completed(bpod.session.current_trial.export())

    op.plot_bars(trial_data, ax=ax_bars)
    psyfun_df = op.update_psyfun_df(trial_data, psyfun_df)
    op.plot_psyfun(trial_data, psyfun_df, ax=ax_psyc)

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
TRIAL NUM:            {trial_data['trial_num']}
STIM POSITION:        {trial_data['position']}
STIM CONTRAST:        {trial_data['contrast']}
STIM PHASE:           {trial_data['stim_phase']}

BLOCK LENGTH:         {trial_data['block_len']}
BLOCK NUMBER:         {trial_data['block_num']}
TRIALS IN BLOCK:      {trial_data['block_trial_num']}
STIM PROB LEFT:       {trial_data['stim_probability_left']}

RESPONSE TIME:        {trial_data['response_time_buffer'][-1]}
TRIAL CORRECT:        {trial_data['trial_correct']}

NTRIALS CORRECT:      {trial_data['ntrials_correct']}
NTRIALS ERROR:        {trial_data['trial_num'] - trial_data['ntrials_correct']}
WATER DELIVERED:      {trial_data['water_delivered']}
TIME FROM START:      {trial_data['elapsed_time']}
AMBIENT SENSOR DATA:  {as_msg}
##########################################"""
    log.info(msg)

    warn_msg = f"""
        ##########################################
                NOT FOUND: SYNC PULSES
        ##########################################
        VISUAL STIMULUS SYNC: {bnc1_msg}
        SOUND SYNC: {bnc2_msg}
        CAMERA SYNC: {port1_msg}
        ##########################################"""
    if not ev_bnc1 or not ev_bnc2 or not ev_port1:
        log.warning(warn_msg)

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
        [log.warning(msg) for x in range(5)]

bpod.close()


if __name__ == '__main__':
    print('main')
