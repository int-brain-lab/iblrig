import logging

import numpy as np
from pybpodapi.protocol import StateMachine

from iblrig.base_choice_world import BiasedChoiceWorldSession


log = logging.getLogger("iblrig")

REWARD_AMOUNTS = (1, 3)


class Session(BiasedChoiceWorldSession):
    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.trials_table['omit_feedback'] = np.zeros(self.trials_table.shape[0], dtype=bool)
        self.trials_table['choice_delay'] = np.zeros(self.trials_table.shape[0], dtype=np.float32)

    def next_trial(self):
        super(Session, self).next_trial()
        # then there is a probability of omitting feedback regardless of the choice
        self.trials_table.at[self.trial_num, 'omit_feedback'] = np.random.random() < self.task_params.OMIT_FEEDBACK_PROBABILITY
        # then drawing the the delay for the choice
        self.trials_table.at[self.trial_num, 'choice_delay'] = np.random.choice([1.5, 3.0], p=[2 / 3, 1 / 3])
        # the reward is a draw within an uniform distribution between 3 and 1
        self.trials_table.at[self.trial_num, 'reward_amount'] = np.random.choice(REWARD_AMOUNTS, p=[.6, .4])

    @property
    def omit_feedback(self):
        return self.trials_table.at[self.trial_num, 'omit_feedback']

    @property
    def choice_to_feedback_delay(self):
        return self.trials_table.at[self.trial_num, 'choice_delay']


class SessionRelatedBlocks(Session):
    """
    IN this scenario, the blocks define a poor and a rich side.
    The probability blocks and reward blocks structure is staggered so that we explore all configurations every 4 blocks
    P0 P1 P2 P1 P2 P1 P2 P1 P2
    R0 R1 R1 R2 R2 R1 R1 R2 R2
    """
    # from iblrig_tasks._iblrig_tasks_neuroModulatorChoiceWorld.task import SessionRelatedBlocks
    # sess = SessionRelatedBlocks()
    def __init__(self, *args, **kwargs):
        super(SessionRelatedBlocks, self).__init__(*args, **kwargs)
        self.trials_table['omit_feedback'] = np.zeros(self.trials_table.shape[0], dtype=bool)
        self.trials_table['choice_delay'] = np.zeros(self.trials_table.shape[0], dtype=np.float32)
        self.blocks_table['probability_left_rich'] = np.zeros(self.blocks_table.shape[0], dtype=np.float32)
        self.BLOCK_REWARD_STAGGER = np.random.randint(0, 2)

    def new_block(self):
        super(Session, self).new_block()
        if self.block_num == 0:
            probability_left_rich = 0.5
        else:
            if int((self.block_num + self.BLOCK_REWARD_STAGGER) / 2 % 2):
                probability_left_rich = 0.8
            else:
                probability_left_rich = 0.2
        self.blocks_table.at[self.block_num, 'probability_left_rich'] = probability_left_rich


    def next_trial(self):
        super(SessionRelatedBlocks, self).next_trial()
        self.trials_table.at[self.trial_num, 'reward_amount'] = self.draw_reward_amount()

    def draw_reward_amount(self):
        # FIXME check: this has 0.5 probability of being correct !!!
        REWARD_AMOUNTS = (1, 3)  # poor and rich
        plr = self.blocks_table.at[self.block_num, 'probability_left_rich']
        if np.sign(self.position):
            probas = [plr, (1 - plr)]  # right
        else:
            probas = [(1 - plr), plr]  # left
        return np.random.choice(REWARD_AMOUNTS, p=probas)


def run():
    sess = SessionRelatedBlocks(interactive=False)

    for i in range(sess.task_params.NTRIALS):  # Main loop
        sess.next_trial()
        log.info(f"Starting trial: {i + 1}")
        # =============================================================================
        #     Start state machine definition
        # =============================================================================
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
            output_actions=[sess.bpod.actions.rotary_encoder_reset],
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
            output_actions=[sess.bpod.actions.bonsai_show_stim],
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
            output_actions=[sess.bpod.actions.rotary_encoder_reset],
            state_change_conditions={"Tup": "closed_loop"},
        )

        if sess.null_feedback:
            sma.add_state(
                state_name="closed_loop",
                state_timer=sess.task_params.RESPONSE_WINDOW,
                output_actions=[sess.bpod.actions.bonsai_closed_loop],
                state_change_conditions={
                    "Tup": "null_feedback",
                    sess.event_error: "null_feedback",
                    sess.event_reward: "null_feedback",
                },
            )

            sma.add_state(
                state_name="null_feedback",
                state_timer=(sess.task_params.FEEDBACK_NOGO_DELAY_SECS
                             + sess.task_params.FEEDBACK_ERROR_DELAY_SECS
                             + sess.task_params.FEEDBACK_CORRECT_DELAY_SECS) / 3,
                output_actions=[],
                state_change_conditions={"Tup": "correct"},
            )

        else:
            sma.add_state(
                state_name="closed_loop",
                state_timer=sess.task_params.RESPONSE_WINDOW,
                output_actions=[sess.bpod.actions.bonsai_closed_loop],
                state_change_conditions={
                    "Tup": "delay_no_go",
                    sess.event_error: "delay_error",
                    sess.event_reward: "freeze_reward",
                },
            )

            sma.add_state(
                state_name="delay_no_go",
                state_timer=sess.choice_to_feedback_delay,
                state_change_conditions={"Tup": "no_go"},
                output_actions=[],
            )

            sma.add_state(
                state_name="no_go",
                state_timer=sess.task_params.FEEDBACK_NOGO_DELAY_SECS,
                output_actions=[sess.bpod.actions.bonsai_hide_stim, sess.sound.OUT_NOISE],
                state_change_conditions={"Tup": "exit_state"},
            )

            sma.add_state(
                state_name="delay_error",
                state_timer=sess.choice_to_feedback_delay,
                state_change_conditions={"Tup": "freeze_error"},
                output_actions=[],
            )

            sma.add_state(
                state_name="freeze_error",
                state_timer=0,
                output_actions=[sess.bpod.actions.bonsai_freeze_stim],
                state_change_conditions={"Tup": "error"},
            )

            sma.add_state(
                state_name="error",
                state_timer=sess.task_params.FEEDBACK_ERROR_DELAY_SECS,
                output_actions=[sess.sound.OUT_NOISE],
                state_change_conditions={"Tup": "hide_stim"},
            )

            sma.add_state(
                state_name="delay_reward",
                state_timer=sess.choice_to_feedback_delay,
                state_change_conditions={"Tup": "freeze_reward"},
                output_actions=[],
            )

            sma.add_state(
                state_name="freeze_reward",
                state_timer=0,
                output_actions=[sess.bpod.actions.bonsai_freeze_stim],
                state_change_conditions={"Tup": "reward"},
            )

            sma.add_state(
                state_name="reward",
                state_timer=sess.reward_time,
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
            output_actions=[[sess.bpod.actions.bonsai_hide_stim]],
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
        sess.bpod.send_state_machine(sma)
        # Run state machine
        if not sess.bpod.run_state_machine(sma):  # Locks until state machine 'exit' is reached
            break

        sess.trial_completed(sess.bpod.session.current_trial.export())
        sess.show_trial_log()
        sess.check_sync_pulses()

    sess.bpod.close()


if __name__ == "__main__":
    run()
