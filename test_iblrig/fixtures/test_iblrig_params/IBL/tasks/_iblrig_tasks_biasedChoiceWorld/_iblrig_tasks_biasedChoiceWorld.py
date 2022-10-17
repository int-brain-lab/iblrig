#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
import logging

import iblrig.bonsai as bonsai
import matplotlib.pyplot as plt
import user_settings
from iblrig.bpod_helper import BpodMessageCreator
from iblrig.user_input import ask_session_delay
from pybpodapi.protocol import Bpod, StateMachine

import online_plots as op
import task_settings
from session_params import SessionParamHandler
from trial_params import TrialParamHandler

log = logging.getLogger("iblrig")

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
    elif data == 1:
        sph.play_tone()
    elif data == 2:
        sph.play_noise()
    elif data == 3:
        sph.start_camera_recording()
    # elif data == 4:
    #     sph.start_visual_stim()

    # sph.OSC_CLIENT.send_message("/e", data)


# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()

# Loop handler function is used to flush events for the online plotting
bpod.loop_handler = bpod_loop_handler
# Soft code handler function can run arbitrary code from within state machine
bpod.softcode_handler_function = softcode_handler
# Bpod message creator
msg = BpodMessageCreator(bpod)
re_reset = msg.rotary_encoder_reset()
bonsai_hide_stim = msg.bonsai_hide_stim()
bonsai_show_stim = msg.bonsai_show_stim()
bonsai_close_loop = msg.bonsai_close_loop()
bonsai_freeze_stim = msg.bonsai_freeze_stim()
sc_play_tone = msg.sound_card_play_idx(sph.GO_TONE_IDX)
sc_play_noise = msg.sound_card_play_idx(sph.WHITE_NOISE_IDX)
bpod = msg.return_bpod()


# Delay initiation
sph.SESSION_START_DELAY_SEC = ask_session_delay(sph.SETTINGS_FILE_PATH)

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================
global tph
tph = TrialParamHandler(sph)

f, axes = op.make_fig(sph)
plt.pause(1)

# =====================================================================
# RUN CAMERA SETUP
# =====================================================================
if bonsai.launch_cameras():
    bonsai.start_camera_setup()

for i in range(sph.NTRIALS):  # Main loop
    tph.next_trial()
    log.info(f"Starting trial: {i + 1}")
    # =============================================================================
    #     Start state machine definition
    # =============================================================================
    sma = StateMachine(bpod)

    if i == 0:  # First trial exception start camera
        log.info("First trial initializing, will move to next trial only if:")
        log.info("1. camera is detected")
        log.info(f"2. {sph.SESSION_START_DELAY_SEC} sec have elapsed")
        sma.add_state(
            state_name="trial_start",
            state_timer=0,
            state_change_conditions={"Port1In": "delay_initiation"},
            output_actions=[("SoftCode", 3)],
        )  # start camera
    else:
        sma.add_state(
            state_name="trial_start",
            state_timer=0,  # ~100µs hardware irreducible delay
            state_change_conditions={"Tup": "reset_rotary_encoder"},
            output_actions=[tph.out_stop_sound],
        )  # stop all sounds
        # TODO: remove out things from tph put in sph
    sma.add_state(
        state_name="delay_initiation",
        state_timer=tph.session_start_delay_sec,
        output_actions=[],
        state_change_conditions={"Tup": "reset_rotary_encoder"},
    )

    sma.add_state(
        state_name="reset_rotary_encoder",
        state_timer=0,
        output_actions=[("Serial1", re_reset)],
        state_change_conditions={"Tup": "quiescent_period"},
    )

    sma.add_state(  # '>back' | '>reset_timer'
        state_name="quiescent_period",
        state_timer=tph.quiescent_period,
        output_actions=[],
        state_change_conditions={
            "Tup": "stim_on",
            tph.movement_left: "reset_rotary_encoder",
            tph.movement_right: "reset_rotary_encoder",
        },
    )

    sma.add_state(
        state_name="stim_on",
        state_timer=0.1,
        output_actions=[("Serial1", bonsai_show_stim)],
        state_change_conditions={
            "Tup": "interactive_delay",
            "BNC1High": "interactive_delay",
            "BNC1Low": "interactive_delay",
        },
    )

    sma.add_state(
        state_name="interactive_delay",
        state_timer=tph.interactive_delay,
        output_actions=[],
        state_change_conditions={"Tup": "play_tone"},
    )

    sma.add_state(
        state_name="play_tone",
        state_timer=0.1,
        output_actions=[tph.out_tone],
        state_change_conditions={
            "Tup": "reset2_rotary_encoder",
            "BNC2High": "reset2_rotary_encoder",
        },
    )

    sma.add_state(
        state_name="reset2_rotary_encoder",
        state_timer=0,
        output_actions=[("Serial1", re_reset)],
        state_change_conditions={"Tup": "closed_loop"},
    )

    sma.add_state(
        state_name="closed_loop",
        state_timer=tph.response_window,
        output_actions=[("Serial1", bonsai_close_loop)],
        state_change_conditions={
            "Tup": "no_go",
            tph.event_error: "freeze_error",
            tph.event_reward: "freeze_reward",
        },
    )

    sma.add_state(
        state_name="no_go",
        state_timer=tph.iti_error,
        output_actions=[("Serial1", bonsai_hide_stim), tph.out_noise],
        state_change_conditions={"Tup": "exit_state"},
    )

    sma.add_state(
        state_name="freeze_error",
        state_timer=0,
        output_actions=[("Serial1", bonsai_freeze_stim)],
        state_change_conditions={"Tup": "error"},
    )

    sma.add_state(
        state_name="error",
        state_timer=tph.iti_error,
        output_actions=[tph.out_noise],
        state_change_conditions={"Tup": "hide_stim"},
    )

    sma.add_state(
        state_name="freeze_reward",
        state_timer=0,
        output_actions=[("Serial1", bonsai_freeze_stim)],
        state_change_conditions={"Tup": "reward"},
    )

    sma.add_state(
        state_name="reward",
        state_timer=tph.reward_valve_time,
        output_actions=[("Valve1", 255)],
        state_change_conditions={"Tup": "correct"},
    )

    sma.add_state(
        state_name="correct",
        state_timer=tph.iti_correct,
        output_actions=[],
        state_change_conditions={"Tup": "hide_stim"},
    )

    sma.add_state(
        state_name="hide_stim",
        state_timer=0.1,
        output_actions=[("Serial1", bonsai_hide_stim)],
        state_change_conditions={
            "Tup": "exit_state",
            "BNC1High": "exit_state",
            "BNC1Low": "exit_state",
        },
    )

    sma.add_state(
        state_name="exit_state",
        state_timer=0.5,
        output_actions=[],
        state_change_conditions={"Tup": "exit"},
    )

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    if not bpod.run_state_machine(sma):  # Locks until state machine 'exit' is reached
        break

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
            f.patch.set_facecolor("xkcd:mint green")
        elif stop_crit == 2:
            msg = "STOPPING CRITERIA Nº2: PLEASE STOP TASK AND REMOVE MOUSE\
            \nMouse seems to be inactive"
            f.patch.set_facecolor("xkcd:yellow")
        elif stop_crit == 3:
            msg = "STOPPING CRITERIA Nº3: PLEASE STOP TASK AND REMOVE MOUSE\
            \n> 90 minutes have passed since session start"
            f.patch.set_facecolor("xkcd:red")

        if not sph.SUBJECT_DISENGAGED_TRIGGERED and stop_crit:
            patch = {
                "SUBJECT_DISENGAGED_TRIGGERED": stop_crit,
                "SUBJECT_DISENGAGED_TRIALNUM": i + 1,
            }
            sph.patch_settings_file(patch)
        [log.warning(msg) for x in range(5)]

bpod.close()


if __name__ == "__main__":
    print("main")
