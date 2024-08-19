import logging
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yaml

import iblrig.misc
from iblrig.base_choice_world import ChoiceWorldSession

log = logging.getLogger('iblrig.task')

# read defaults from task_parameters.yaml
with open(Path(__file__).parent.joinpath('task_parameters.yaml')) as f:
    DEFAULTS = yaml.safe_load(f)


class Session(ChoiceWorldSession):
    protocol_name = '_iblrig_tasks_passiveChoiceWorld'

    def __init__(
        self,
        *args,
        session_template_id=0,
        duration_spontaneous: int = DEFAULTS['SPONTANEOUS_ACTIVITY_SECONDS'],
        skip_event_replay: bool = DEFAULTS['SKIP_EVENT_REPLAY'],
        **kwargs,
    ):
        self.extractor_tasks = ['PassiveRegisterRaw', 'PassiveTask']
        super(ChoiceWorldSession, self).__init__(**kwargs)
        self.task_params.SESSION_TEMPLATE_ID = session_template_id
        all_trials = pd.read_parquet(Path(__file__).parent.joinpath('passiveChoiceWorld_trials_fixtures.pqt'))
        self.trials_table = all_trials[all_trials['session_id'] == self.task_params.SESSION_TEMPLATE_ID].copy()
        self.trials_table['reward_valve_time'] = self.compute_reward_time(amount_ul=self.trials_table['reward_amount'])
        assert duration_spontaneous < 60 * 60 * 24
        self.task_params['SPONTANEOUS_ACTIVITY_SECONDS'] = duration_spontaneous
        self.task_params['SKIP_EVENT_REPLAY'] = skip_event_replay
        if self.hardware_settings['MAIN_SYNC']:
            log.error('PassiveChoiceWorld extraction not supported for Bpod-only sessions!')

    @staticmethod
    def extra_parser():
        """:return: argparse.parser()"""
        parser = super(Session, Session).extra_parser()
        parser.add_argument(
            '--session_template_id',
            option_strings=['--session_template_id'],
            dest='session_template_id',
            default=0,
            type=int,
            help='pre-generated session index (zero-based)',
        )
        parser.add_argument(
            '--duration_spontaneous',
            option_strings=['--duration_spontaneous'],
            dest='duration_spontaneous',
            default=DEFAULTS['SPONTANEOUS_ACTIVITY_SECONDS'],
            type=int,
            help=f'duration of spontaneous activity in seconds ' f'(default: {DEFAULTS["SPONTANEOUS_ACTIVITY_SECONDS"]} s)',
        )
        parser.add_argument(
            '--skip_event_replay',
            option_strings=['--skip_event_replay'],
            action='store_true',
            dest='skip_event_replay',
            help='skip replay of events',
        )
        return parser

    def start_hardware(self):
        if not self.is_mock:
            self.start_mixin_frame2ttl()
            self.start_mixin_bpod()
            self.start_mixin_valve()
            self.start_mixin_sound()
            self.start_mixin_bonsai_cameras()
            self.start_mixin_bonsai_microphone()
            self.start_mixin_rotary_encoder()

    def get_state_machine_trial(self, *args, **kwargs):
        pass

    def next_trial(self):
        pass

    def _run(self):
        """Run the task with the actual state machine."""
        self.trigger_bonsai_cameras()

        # Run the passive part i.e. spontaneous activity and RFMapping stim
        self.run_passive_visual_stim(sa_time=timedelta(seconds=self.task_params['SPONTANEOUS_ACTIVITY_SECONDS']))

        if self.task_params['SKIP_EVENT_REPLAY'] is True:
            log.info('Skipping replay of task events')
            return

        # run the replay of task events: V for valve, T for tone, N for noise, G for gratings
        log.info('Starting replay of task events')
        action_show_stim = self.bpod.actions['bonsai_show_stim'][1]
        action_hide_stim = self.bpod.actions['bonsai_hide_stim'][1]
        byte_show_stim = self.bpod.serial_messages[action_show_stim]['message'][-1]
        byte_hide_stim = self.bpod.serial_messages[action_hide_stim]['message'][-1]

        if not self.is_mock:
            self.start_mixin_bonsai_visual_stimulus()
        for trial_num, trial in self.trials_table.iterrows():
            self.trial_num = trial_num
            log.info(f'Delay: {trial.stim_delay}; ID: {trial.stim_type}; Count: {self.trial_num}/300')
            sys.stdout.flush()
            time.sleep(trial.stim_delay)
            if trial.stim_type == 'V':
                self.valve_open(self.reward_time)
            elif trial.stim_type == 'T':
                self.sound_play_tone(state_timer=0.102)
            elif trial.stim_type == 'N':
                self.sound_play_noise(state_timer=0.510)
            elif trial.stim_type == 'G':
                # this will send the current trial info to the visual stim
                # we need to make sure Bonsai is in a state to display stimuli
                self.send_trial_info_to_bonsai()
                self.bonsai_visual_udp_client.send_message(r'/re', byte_show_stim)
                time.sleep(0.3)
                self.bonsai_visual_udp_client.send_message(r'/re', byte_hide_stim)
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break


if __name__ == '__main__':  # pragma: no cover
    # python .\iblrig_tasks\_iblrig_tasks_spontaneous\task.py --subject mysubject
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
