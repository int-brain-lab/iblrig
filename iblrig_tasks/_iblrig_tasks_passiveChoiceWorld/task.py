import logging
import sys
import time
from pathlib import Path

import pandas as pd

import iblrig.misc
from iblrig.base_choice_world import ChoiceWorldSession

log = logging.getLogger('iblrig.task')


class Session(ChoiceWorldSession):
    protocol_name = '_iblrig_tasks_passiveChoiceWorld'
    extractor_tasks = ['PassiveRegisterRaw', 'PassiveTask']

    def __init__(self, *args, session_template_id=0, **kwargs):
        super(ChoiceWorldSession, self).__init__(**kwargs)
        self.task_params.SESSION_TEMPLATE_ID = session_template_id
        all_trials = pd.read_parquet(Path(__file__).parent.joinpath('passiveChoiceWorld_trials_fixtures.pqt'))
        self.trials_table = all_trials[all_trials['session_id'] == self.task_params.SESSION_TEMPLATE_ID].copy()
        self.trials_table['reward_valve_time'] = self.compute_reward_time(amount_ul=self.trials_table['reward_amount'])

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
        """
        This is the method that runs the task with the actual state machine
        :return:
        """
        self.trigger_bonsai_cameras()
        log.info('Starting spontaneous activity followed by receptive field mapping')
        # Run the passive part i.e. spontaneous activity and RFMapping stim
        self.run_passive_visual_stim(sa_time='00:10:00')
        # Then run the replay of task events: V for valve, T for tone, N for noise, G for gratings
        log.info('Starting replay of task stims')

        # extract rotary encoder port number and message for showing garbor stimulus
        re_port_str, show_stim_value = self.bpod.actions.bonsai_show_stim
        re_port = int(re_port_str[-1])

        if not self.is_mock:
            self.start_mixin_bonsai_visual_stimulus()
        for self.trial_num, trial in self.trials_table.iterrows():
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
                self.bpod.manual_override(2, 'Serial', channel_number=re_port, value=show_stim_value)
                self.bonsai_visual_udp_client.send_message(r'/re', 2)  # show_stim 2
                time.sleep(0.3)
                self.bonsai_visual_udp_client.send_message(r'/re', 1)  # stop_stim 1
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break


if __name__ == '__main__':  # pragma: no cover
    # python .\iblrig_tasks\_iblrig_tasks_spontaneous\task.py --subject mysubject
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
