# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
# @Last Modified by:   N
# @Last Modified time: 2018-03-06 11:50:27

from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
import subprocess
import time
import shutil
from session_params import session_param_handler, rotary_encoder
from trial_params import trial_param_handler
import task_settings
import online_plots as op

global sph
sph = session_param_handler(task_settings)
re = rotary_encoder(sph.ROTARY_ENCODER_PORT, sph.STIM_POSITIONS,
                    sph.QUIESCENCE_THRESHOLDS, sph.STIM_GAIN)
re.configure(RotaryEncoderModule)


def my_softcode_handler(data):
    """
    Soft codes should work with resasonable latency considering our limiting
    factor is the refresh rate of the screen which should be 16.667ms @ a frame
    rate of 60Hz
    OSC dictionary:
    10 = stim_on INIT
    20 = closed_loop INIT
    30 = stim_off INIT
    40 = play error tone
    99 = Client connected
    """
    global sph
    if data == 20:
        sph.SD.play(sph.GO_TONE, sph.SOUND_SAMPLE_FREQ)
    elif data == 40:
        sph.SD.play(sph.WHITE_NOISE, sph.SOUND_SAMPLE_FREQ)

    sph.OSC_CLIENT.send_message("/e", data)


# =============================================================================
# RUN BONSAI
# =============================================================================
if sph.USE_VISUAL_STIMULUS:
    # Copy stimulus folder with bonsai workflow
    src = 'C:\\iblrig\\visual_stim\\Gabor2D\\'
    dst = sph.SESSION_DATA_FOLDER + 'Gabor2D\\'
    shutil.copytree(src, dst)

    bns = 'C:\\Users\\User\\AppData\\Local\\Bonsai\\Bonsai64.exe'
    wkfl = sph.SESSION_DATA_FOLDER + 'Gabor2D\\Gabor2Dv0.3.bonsai'
    flags = '--start'  # --noeditor

    bonsai = subprocess.Popen([bns, wkfl, flags])
    time.sleep(5)
# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()
# Rotary Encoder State Machine handler
rotary_encoder = list(bpod.modules)[0]  # TODO:BETTER!
# Set soft code handler function
bpod.softcode_handler_function = my_softcode_handler

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
tph = trial_param_handler(sph)

# f, ax_bars, ax_psyc = op.make_fig()
# psyfun_df = op.make_psyfun_df()

for i in range(sph.NTRIALS):  # Main loop
    print('Starting trial: ', i + 1)
    tph.next_trial()
    tph.send_current_trial_info(osc_client=sph.OSC_CLIENT,
                                trial_num=tph.trial_num,
                                t_position=tph.position,
                                t_contrast=tph.contrast,
                                t_freq=sph.STIM_FREQ,
                                t_angle=sph.STIM_ANGLE,
                                t_gain=sph.STIM_GAIN,
                                t_sigma=sph.STIM_SIGMA)
# =============================================================================
#     Start state machine definition
# =============================================================================
    sma = StateMachine(bpod)

    sma.add_state(
        state_name='trial_start',
        state_timer=0.001,
        state_change_conditions={'Tup': sph.STATE_AFTER_START},
        output_actions=[('SoftCode', 30),  # Stop the stim
                        ('Serial1', ord('Z'))])

    sma.add_state(
        state_name='quiescent_period',
        state_timer=tph.quiescent_period,
        state_change_conditions={'Tup': 'stim_on',
                                 tph.movement_left: 'trial_start',
                                 tph.movement_right: 'trial_start'},
        output_actions=[(OutputChannel.Serial1, ord('E'))])
    # TODO: load_serial_message!!

    sma.add_state(
        state_name='stim_on',
        state_timer=tph.interactive_delay,
        state_change_conditions={'Tup': 'closed_loop'},
        output_actions=[(OutputChannel.SoftCode, 10)])  # show the stim

    sma.add_state(  # reset 0
        state_name='closed_loop',
        state_timer=0.001,
        state_change_conditions={'Tup': 'closed_loop2'},
        output_actions=[('Serial1', ord('Z')),  # set 0 pos
                        ])
    sma.add_state(  # reset threshold
        state_name='closed_loop2',
        state_timer=tph.response_window,  # FIX: points to nothing!!!!
        state_change_conditions={tph.event_error: 'error',
                                 tph.event_reward: 'reward'},
        output_actions=[('Serial1', ord('E')),  # reset all thresh
                        # start closed_loop + play go tone
                        (OutputChannel.SoftCode, 20),
                        ])
    sma.add_state(
        state_name='reward',
        state_timer=tph.reward_valve_time,
        state_change_conditions={'Tup': 'correct'},
        output_actions=[('Valve1', 1),
                        ])
    sma.add_state(  # TODO: check if sound outputs or not
        state_name='no_go',
        state_timer=tph.iti_error,  # WHAT ITI?
        state_change_conditions={'Tup': 'exit'},
        output_actions=[('SoftCode', 40),  # play white noise
                        ])
    sma.add_state(
        state_name='error',
        state_timer=tph.iti_error,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[('SoftCode', 40),  # play white noise
                        ])
    sma.add_state(
        state_name='correct',
        state_timer=tph.iti_correct,
        state_change_conditions={'Tup': 'exit'},
        output_actions=[])  # stim stays on for iti correct

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)

    # Run state machine
    bpod.run_state_machine(sma)

    trial_data = tph.trial_completed(bpod.session.current_trial.export())
    # op.plot_bars(trial_data, sph.TARGET_REWARD, ax=ax_bars)
    # psyfun_df = op.update_psyfun_df(trial_data, psyfun_df)
    # op.plot_psyfun(trial_data, psyfun_df, ax=ax_psyc)
    # f.show()
    bdata = op.get_barplot_data(trial_data, 3)
    print('\nTRIAL NUM: ', bdata['trial_num'])
    print('\nNTRIALS CORRECT: ', bdata['ntrials_correct'])
    print('\nWATER DELIVERED ', bdata['water_delivered'])
    print('TIME FROM START: ', bdata['time_from_start'])

bpod.close()


if __name__ == '__main__':
    print('main')
