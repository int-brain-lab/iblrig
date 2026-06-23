*****************
Deprecation Notes
*****************


8.28.0: Handling of Camera and Initial Delay
============================================

With release 8.28.0 of IBLRIG, handling of the camera initialization and the session's initial delay has been moved out of :py:class:`~iblrig.base_choice_world.ChoiceWorldSession`'s state machine definition.

Previously, :py:meth:`~iblrig.base_choice_world.ChoiceWorldSession.get_state_machine_trial` would define the first trials as such:

.. code-block:: python

    def get_state_machine_trial(self, i):
        # we define the trial number here for subclasses that may need it
        sma = self._instantiate_state_machine(trial_number=i)

        if i == 0:  # First trial exception start camera
            session_delay_start = self.task_params.get('SESSION_DELAY_START', 0)
            log.info('First trial initializing, will move to next trial only if:')
            log.info('1. camera is detected')
            log.info(f'2. {session_delay_start} sec have elapsed')
            sma.add_state(
                state_name='trial_start',
                state_timer=0,
                state_change_conditions={'Port1In': 'delay_initiation'},
                output_actions=[('SoftCode', SOFTCODE.TRIGGER_CAMERA), ('BNC1', 255)],
            )  # start camera
            sma.add_state(
                state_name='delay_initiation',
                state_timer=session_delay_start,
                output_actions=[],
                state_change_conditions={'Tup': 'reset_rotary_encoder'},
            )
        else:
            sma.add_state(
                state_name='trial_start',
                state_timer=0,  # ~100µs hardware irreducible delay
                state_change_conditions={'Tup': 'reset_rotary_encoder'},
                output_actions=[self.bpod.actions.stop_sound, ('BNC1', 255)],
            )  # stop all sounds

        # [...]

This has been reduced to the following:

.. code-block:: python

    def get_state_machine_trial(self, i):
        # we define the trial number here for subclasses that may need it
        sma = self._instantiate_state_machine(trial_number=i)

        # Signal trial start and stop all sounds
        sma.add_state(
            state_name='trial_start',
            state_timer=0,  # ~100µs hardware irreducible delay
            state_change_conditions={'Tup': 'reset_rotary_encoder'},
            output_actions=[self.bpod.actions.stop_sound, ('BNC1', 255)],
        )

        # [...]

If your custom task inherits from :py:class:`~iblrig.base_choice_world.ChoiceWorldSession` and overrides :py:meth:`~iblrig.base_choice_world.ChoiceWorldSession.get_state_machine_trial` adapt it accordingly.
