# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-06-26 17:23:39
from pybpodapi.protocol import Bpod, StateMachine
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
from pybpod_rotaryencoder_module.module import RotaryEncoder
import matplotlib.pyplot as plt
from dateutil import parser
import datetime

from session_params import session_param_handler
from trial_params import trial_param_handler
import ambient_sensor
import task_settings
import user_settings
import online_plots as op

global sph
sph = session_param_handler(task_settings, user_settings)


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

# SoundCard
if not sph.SOFT_SOUND:
    sound_board = [x for x in bpod.modules if x.name == 'SoundBoard1'][0]
    sound_board_i2 = 5
    sound_board_i3 = 6
    sound_board_i4 = 7
    bpod.load_serial_message(sound_board, sound_board_i2, [ord('P'), 2])
    bpod.load_serial_message(sound_board, sound_board_i3, [ord('P'), 3])
    bpod.load_serial_message(sound_board, sound_board_i4, [ord('P'), 4])
# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
tph = trial_param_handler(sph)

f, ax_bars, ax_psyc = op.make_fig()
psyfun_df = op.make_psyfun_df()
plt.pause(1)

for i in range(sph.NTRIALS):  # Main loop
    tph.next_trial()
    print('\n\nStarting trial: ', i + 1)
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)
    sma.set_global_timer(timer_id=1, timer_duration=0.3, on_set_delay=0,
                         channel=bpod.OutputChannels.BNC2, on_message=1, 
                         off_message=0)

    sma.add_state(
        state_name='trial_start',
        state_timer=0.2,  # ~100µs hardware irreducible delay
        state_change_conditions={'Tup': 'reset_rotary_encoder'},
        output_actions=[('Serial1', rotary_encoder_e1),
                        ('SoftCode', 0),
                        ('GlobalTimerTrig', 1),
                        ('BNC2', 1),
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
        state_timer=tph.response_window,  # 3600 no_go will be inexistent
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

    print('\nTRIAL NUM: ', trial_data['trial_num'])
    print('NTRIALS CORRECT: ', trial_data['ntrials_correct'])
    print('WATER DELIVERED ', trial_data['water_delivered'])
    print('TIME FROM START: ', (datetime.datetime.now() -
                                  parser.parse(trial_data['init_datetime'])))
    if sph.RECORD_AMBIENT_SENSOR_DATA:
        data = ambient_sensor.get_reading(bpod,
                                          save_to=sph.SESSION_RAW_DATA_FOLDER)
        print('AMBIENT SENSOR DATA: ', data)


bpod.close()


if __name__ == '__main__':
    print('main')
