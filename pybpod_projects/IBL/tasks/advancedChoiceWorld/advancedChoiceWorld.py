# !/usr/bin/python3
# -*- coding: utf-8 -*-
from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
import subprocess
import time
from session_params import session_param_handler, rotary_encoder
from trial_params import trial_param_handler
import task_settings

global sph
sph = session_param_handler(task_settings)
re = rotary_encoder(sph.ROTARY_ENCODER_PORT, sph.STIM_POSITIONS, sph.STIM_GAIN)
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
    bns = 'C:\\Users\\User\\AppData\\Local\\Bonsai\\Bonsai.exe'
    wkfl = 'C:\\iblrig\\Bonsai_workflows\\STIM\\Gabor2D\\Gabor2Dv0.3.bonsai'
    flags = '--start'
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

for i in range(sph.NTRIALS):
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
        state_name='stim_on',
        state_timer=tph.interactive_delay,
        state_change_conditions={EventName.Tup: 'closed_loop'},
        output_actions=[(OutputChannel.SoftCode, 10)])  # show the stim

    sma.add_state(  # reset 0 + threshold
        state_name='closed_loop',
        state_timer=0.001,
        state_change_conditions={EventName.Tup: 'closed_loop2'},
        output_actions=[(OutputChannel.Serial1, ord('Z')),  # set 0 pos
                        ])
    sma.add_state(  # reset 0 + threshold
        state_name='closed_loop2',
        state_timer=tph.response_window,
        state_change_conditions={tph.event_error: 'error',
                                 tph.event_reward: 'reward'},
        output_actions=[(OutputChannel.Serial1, ord('E')),  # reset all thresh
                        (OutputChannel.SoftCode, 20),  # go tone + closed loop
                        ])
    sma.add_state(
        state_name='reward',
        state_timer=tph.reward_valve_time,
        state_change_conditions={EventName.Tup: 'correct'},
        output_actions=[(OutputChannel.ValveState, 1),
                        ])
    sma.add_state(
        state_name='error',
        state_timer=tph.iti_error,
        state_change_conditions={EventName.Tup: 'iti'},
        output_actions=[(OutputChannel.SoftCode, 40),  # play white noise
                        ])
    sma.add_state(
        state_name='correct',
        state_timer=tph.iti_correct,
        state_change_conditions={EventName.Tup: 'iti'},
        output_actions=[])  # stim stays on for iti correct
    sma.add_state(
        state_name='iti',
        state_timer=tph.iti,
        state_change_conditions={EventName.Tup: 'exit'},
        output_actions=[(OutputChannel.SoftCode, 30)])  # Stop the stim

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)

#    rotary_encoder.enable_positions_threshold()
#    rotary_encoder.set_position_zero()

    # Run state machine
    bpod.run_state_machine(sma)

    trial_data = tph.trial_completed(bpod.session.current_trial.export())
    print(trial_data)
    # print("Current trial info: {0}".format(bpod.session.current_trial))

bpod.stop()

if __name__ == '__main__':
    print('main')
