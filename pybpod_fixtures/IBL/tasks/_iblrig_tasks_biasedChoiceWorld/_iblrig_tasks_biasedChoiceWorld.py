#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 12:31:13
import logging

import iblrig.bonsai as bonsai
import matplotlib.pyplot as plt
from iblrig.bpod_helper import BpodMessageCreator
from iblrig.user_input import ask_session_delay
from pybpodapi.protocol import StateMachine

from task import Session
import online_plots as op

log = logging.getLogger("iblrig")

sess = Session(interactive=False)

def bpod_loop_handler():
    f.canvas.flush_events()  # 100µs

# Bpod message creator
msg = BpodMessageCreator(sess.bpod)


# Delay initiation
sess.task_params.SESSION_START_DELAY_SEC = ask_session_delay(sess.task_params.SETTINGS_FILE_PATH)

# =============================================================================
# TRIAL PARAMETERS AND STATE MACHINE
# =============================================================================

plt.pause(1)

# =====================================================================
# RUN CAMERA SETUP
# =====================================================================
if bonsai.launch_cameras():
    bonsai.start_camera_setup()

for i in range(sess.task_params.NTRIALS):  # Main loop
    tph.next_trial()
    log.info(f"Starting trial: {i + 1}")
    # =============================================================================
    #     Start state machine definition
    # =============================================================================
    sma = StateMachine(bpod)

    if i == 0:  # First trial exception start camera
        log.info("First trial initializing, will move to next trial only if:")
        log.info("1. camera is detected")
        log.info(f"2. {sess.task_params.SESSION_START_DELAY_SEC} sec have elapsed")
        sma.add_state(
            state_name="trial_start",
            state_timer=0,
            state_change_conditions={"Port1In": "delay_initiation"},
            output_actions=[("SoftCode", 3), ("BNC1", 255)],
        )  # start camera
    else:
        sma.add_state(
            state_name="trial_start",
            state_timer=0,  # ~100µs hardware irreducible delay
            state_change_conditions={"Tup": "reset_rotary_encoder"},
            output_actions=[tph.out_stop_sound, ("BNC1", 255)],
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
        output_actions=[("Serial1", msg.rotary_encoder_reset())],
        state_change_conditions={"Tup": "quiescent_period"},
    )

    sma.add_state(  # '>back' | '>reset_timer'
        state_name="quiescent_period",
        state_timer=sess.task_params.QUIESCENT_PERIOD,
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
        output_actions=[("Serial1",  msg.bonsai_show_stim())],
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
        output_actions=[("Serial1", msg.rotary_encoder_reset())],
        state_change_conditions={"Tup": "closed_loop"},
    )

    sma.add_state(
        state_name="closed_loop",
        state_timer=tph.response_window,
        output_actions=[("Serial1", msg.bonsai_close_loop())],
        state_change_conditions={
            "Tup": "no_go",
            tph.event_error: "freeze_error",
            tph.event_reward: "freeze_reward",
        },
    )

    sma.add_state(
        state_name="no_go",
        state_timer=tph.iti_error,
        output_actions=[("Serial1", msg.bonsai_hide_stim()), tph.out_noise],
        state_change_conditions={"Tup": "exit_state"},
    )

    sma.add_state(
        state_name="freeze_error",
        state_timer=0,
        output_actions=[("Serial1", msg.bonsai_freeze_stim())],
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
        output_actions=[("Serial1", msg.bonsai_freeze_stim())],
        state_change_conditions={"Tup": "reward"},
    )

    sma.add_state(
        state_name="reward",
        state_timer=tph.reward_valve_time,
        output_actions=[("Valve1", 255), ("BNC1", 255)],
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
        output_actions=[("Serial1", msg.bonsai_hide_stim())],
        state_change_conditions={
            "Tup": "exit_state",
            "BNC1High": "exit_state",
            "BNC1Low": "exit_state",
        },
    )

    sma.add_state(
        state_name="exit_state",
        state_timer=0.5,
        output_actions=[("BNC1", 255)],
        state_change_conditions={"Tup": "exit"},
    )

    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    if not bpod.run_state_machine(sma):  # Locks until state machine 'exit' is reached
        break

    sess.trial_completed(bpod.session.current_trial.export())


    sess.show_trial_log()

    sess.check_sync_pulses()
    stop_crit = sess.check_stop_criterions()
    # clean this up and remove display from logic
    if stop_crit and sess.task_params.USE_AUTOMATIC_STOPPING_CRITERIONS:
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

        if not sess.task_params.SUBJECT_DISENGAGED_TRIGGERED and stop_crit:
            patch = {
                "SUBJECT_DISENGAGED_TRIGGERED": stop_crit,
                "SUBJECT_DISENGAGED_TRIALNUM": i + 1,
            }
            sess.paths.patch_settings_file(patch)
        [log.warning(msg) for x in range(5)]

bpod.close()
