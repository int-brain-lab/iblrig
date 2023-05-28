import datetime
import logging
import sys

from iblrig.base_choice_world import ChoiceWorldSession
import iblrig.test

log = logging.getLogger("iblrig")


class Session(ChoiceWorldSession):
    protocol_name = "_iblrig_tasks_passiveChoiceWorld"

    def __init__(self, duration_secs=None, **kwargs):
        super(ChoiceWorldSession, self).__init__(**kwargs)

    def run(self):
        """
        This is the method that runs the task with the actual state machine
        :return:
        """
        # super(ChoiceWorldSession, self).run()
        log.info("Starting passive protocol")
        import time
        while True:
            time.sleep(1.5)
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break

        # Run the passive part i.e. spontaneous activity and RFMapping stim
        self.run_passive_visual_stim()

        # Then run the replay of task events
        log.info("Starting replay of task stims")
        pcs_idx = 0
        scount = 1
        for sdel, sid in zip(sph.STIM_DELAYS, sph.STIM_IDS):
            log.info(f"Delay: {sdel}; ID: {sid}; Count: {scount}/300")
            sys.stdout.flush()
            time.sleep(sdel)
            if sid == "V":
                # Make bpod task with 1 state = valve_open -> exit
                do_valve_click(bpod, sph.REWARD_VALVE_TIME)
                # time.sleep(sph.REWARD_VALVE_TIME)
            elif sid == "T":
                do_bpod_sound(bpod, sc_play_tone)
                # do_card_sound(card, card_play_tone)
                # time.sleep(0.1)
            elif sid == "N":
                do_bpod_sound(bpod, sc_play_noise)
                # do_card_sound(card, card_play_noise)
                # time.sleep(0.5)
            elif sid == "G":
                do_gabor(
                    sph.OSC_CLIENT,
                    pcs_idx,
                    sph.POSITIONS[pcs_idx],
                    sph.CONTRASTS[pcs_idx],
                    sph.STIM_PHASE[pcs_idx],
                )
                pcs_idx += 1
                # time.sleep(0.3)
            scount += 1

        log.critical("Graceful exit")
        self.session_info.SESSION_END_TIME = datetime.datetime.now().isoformat()
        self.save_task_parameters_to_json_file()
        self.register_to_alyx()


if __name__ == "__main__":
    # python .\iblrig_tasks\_iblrig_tasks_spontaneous\task.py --subject mysubject
    kwargs = iblrig.misc.get_task_runner_argument_parser()
    sess = Session(**kwargs)
    sess.run()
