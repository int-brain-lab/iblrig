import sys
import time
from pathlib import Path

import pandas as pd

import iblrig.misc
from iblrig.base_choice_world import ChoiceWorldSession


class Session(ChoiceWorldSession):
    protocol_name = '_iblrig_tasks_passiveChoiceWorld'
    extractor_tasks = ['PassiveRegisterRaw', 'PassiveTask']

    def __init__(self, **kwargs):
        super(ChoiceWorldSession, self).__init__(**kwargs)
        SESSION_IDX = 0
        all_trials = pd.read_parquet(Path(__file__).parent.joinpath('passiveChoiceWorld_trials_fixtures.pqt'))
        self.trials_table = all_trials[all_trials['session_id'] == SESSION_IDX].copy()
        self.trials_table['reward_valve_time'] = self.compute_reward_time(amount_ul=self.trials_table['reward_amount'])

    def start_hardware(self):
        if not self.is_mock:
            self.start_mixin_frame2ttl()
            self.start_mixin_bpod()
            self.start_mixin_valve()
            self.start_mixin_sound()
            self.start_mixin_bonsai_cameras()
            self.start_mixin_bonsai_microphone()

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
        self.logger.info('Starting spontaneous activity followed by receptive field mapping')
        # Run the passive part i.e. spontaneous activity and RFMapping stim
        self.run_passive_visual_stim(sa_time='00:10:00')
        # Then run the replay of task events: V for valve, T for tone, N for noise, G for gratings
        self.logger.info('Starting replay of task stims')
        for self.trial_num, trial in self.trials_table.iterrows():
            self.logger.info(f'Delay: {trial.stim_delay}; ID: {trial.stim_type}; Count: {self.trial_num}/300')
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
                self.send_trial_info_to_bonsai()
                self.bonsai_visual_udp_client.send_message('/re', 2)  # show_stim 2
                time.sleep(0.3)
                self.bonsai_visual_udp_client.send_message('/re', 1)  # stop_stim 1
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break


if __name__ == '__main__':  # pragma: no cover
    # python .\iblrig_tasks\_iblrig_tasks_spontaneous\task.py --subject mysubject
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
