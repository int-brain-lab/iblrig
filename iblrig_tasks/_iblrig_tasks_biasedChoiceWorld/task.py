import logging

from pybpodapi.protocol import StateMachine

from iblrig.base_choice_world import BiasedChoiceWorldSession


NTRIALS_INIT = 1000
log = logging.getLogger("iblrig")


class Session(BiasedChoiceWorldSession):
    pass


def run(sess=None):

    sess = sess or Session(interactive=False)

    for i in range(sess.task_params.NTRIALS):  # Main loop
        sess.next_trial()
        log.info(f"Starting trial: {i + 1}")

        sma = StateMachine(sess.bpod)

        if i == 0:  # First trial exception start camera
            session_delay_start = sess.task_params.get("SESSION_DELAY_START", 0)
            log.info("First trial initializing, will move to next trial only if:")
            log.info("1. camera is detected")
            log.info(f"2. {session_delay_start} sec have elapsed")
            sma.add_state(
                state_name="trial_start",
                state_timer=0,
                state_change_conditions={"Port1In": "delay_initiation"},
                output_actions=[("SoftCode", 3), ("BNC1", 255)],
            )  # start camera
            sma.add_state(
                state_name="delay_initiation",
                state_timer=session_delay_start,
                output_actions=[],
                state_change_conditions={"Tup": "reset_rotary_encoder"},
            )
        else:
            sma.add_state(
                state_name="trial_start",
                state_timer=0,  # ~100µs hardware irreducible delay
                state_change_conditions={"Tup": "reset_rotary_encoder"},
                output_actions=[sess.sound.OUT_STOP_SOUND, ("BNC1", 255)],
            )  # stop all sounds

        sma.add_state(
            state_name="reset_rotary_encoder",
            state_timer=0,
            output_actions=[("Serial1", sess.bpod.rotary_encoder_reset())],
            state_change_conditions={"Tup": "quiescent_period"},
        )

        sma.add_state(  # '>back' | '>reset_timer'
            state_name="quiescent_period",
            state_timer=sess.quiescent_period,
            output_actions=[],
            state_change_conditions={
                "Tup": "stim_on",
                sess.movement_left: "reset_rotary_encoder",
                sess.movement_right: "reset_rotary_encoder",
            },
        )

        sma.add_state(
            state_name="stim_on",
            state_timer=0.1,
            output_actions=[("Serial1",  sess.bpod.bonsai_show_stim())],
            state_change_conditions={
                "Tup": "interactive_delay",
                "BNC1High": "interactive_delay",
                "BNC1Low": "interactive_delay",
            },
        )

        sma.add_state(
            state_name="interactive_delay",
            state_timer=sess.task_params.INTERACTIVE_DELAY,
            output_actions=[],
            state_change_conditions={"Tup": "play_tone"},
        )

        sma.add_state(
            state_name="play_tone",
            state_timer=0.1,
            output_actions=[sess.sound.OUT_TONE],
            state_change_conditions={
                "Tup": "reset2_rotary_encoder",
                "BNC2High": "reset2_rotary_encoder",
            },
        )

        sma.add_state(
            state_name="reset2_rotary_encoder",
            state_timer=0,
            output_actions=[("Serial1", sess.bpod.rotary_encoder_reset())],
            state_change_conditions={"Tup": "closed_loop"},
        )

        sma.add_state(
            state_name="closed_loop",
            state_timer=sess.task_params.RESPONSE_WINDOW,
            output_actions=[("Serial1", sess.bpod.bonsai_close_loop())],
            state_change_conditions={
                "Tup": "no_go",
                sess.event_error: "freeze_error",
                sess.event_reward: "freeze_reward",
            },
        )

        sma.add_state(
            state_name="no_go",
            state_timer=sess.task_params.FEEDBACK_NOGO_DELAY_SECS,
            output_actions=[("Serial1", sess.bpod.bonsai_hide_stim()), sess.sound.OUT_NOISE],
            state_change_conditions={"Tup": "exit_state"},
        )

        sma.add_state(
            state_name="freeze_error",
            state_timer=0,
            output_actions=[("Serial1", sess.bpod.bonsai_freeze_stim())],
            state_change_conditions={"Tup": "error"},
        )

        sma.add_state(
            state_name="error",
            state_timer=sess.task_params.FEEDBACK_ERROR_DELAY_SECS,
            output_actions=[sess.sound.OUT_NOISE],
            state_change_conditions={"Tup": "hide_stim"},
        )

        sma.add_state(
            state_name="freeze_reward",
            state_timer=0,
            output_actions=[("Serial1", sess.bpod.bonsai_freeze_stim())],
            state_change_conditions={"Tup": "reward"},
        )

        sma.add_state(
            state_name="reward",
            state_timer=sess.valve.reward_time,
            output_actions=[("Valve1", 255), ("BNC1", 255)],
            state_change_conditions={"Tup": "correct"},
        )

        sma.add_state(
            state_name="correct",
            state_timer=sess.task_params.FEEDBACK_CORRECT_DELAY_SECS,
            output_actions=[],
            state_change_conditions={"Tup": "hide_stim"},
        )

        sma.add_state(
            state_name="hide_stim",
            state_timer=0.1,
            output_actions=[("Serial1", sess.bpod.bonsai_hide_stim())],
            state_change_conditions={
                "Tup": "exit_state",
                "BNC1High": "exit_state",
                "BNC1Low": "exit_state",
            },
        )

        sma.add_state(
            state_name="exit_state",
            state_timer=sess.task_params.ITI_DELAY_SECS,
            output_actions=[("BNC1", 255)],
            state_change_conditions={"Tup": "exit"},
        )

        # Send state machine description to Bpod device
        sess.send_state_machine(sma)
        # Run state machine
        if not sess.bpod.run_state_machine(sma):  # Locks until state machine 'exit' is reached
            break

        sess.trial_completed(sess.bpod.session.current_trial.export())
        sess.show_trial_log()
        sess.check_sync_pulses()

    sess.bpod.close()
