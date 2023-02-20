import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class ParameterHandler():
    def __init__(self):
        NTRIALS_INIT = 1000
        self.trials_table = pd.DataFrame({
            "block_num": np.zeros(NTRIALS_INIT, dtype=np.int16),
            "block_trial_num": np.zeros(NTRIALS_INIT, dtype=np.int16),
            "contrast": np.zeros(NTRIALS_INIT),
            "position": np.zeros(NTRIALS_INIT),
            "quiescent_period": np.zeros(NTRIALS_INIT),
            "response_time": np.zeros(NTRIALS_INIT),
            "stim_angle": np.zeros(NTRIALS_INIT),
            "stim_freq": np.zeros(NTRIALS_INIT),
            "stim_gain": np.zeros(NTRIALS_INIT),
            "stim_sigma": np.zeros(NTRIALS_INIT),
            "stim_reverse": np.zeros(NTRIALS_INIT),
            "stim_phase": np.zeros(NTRIALS_INIT),
            "stim_probability_left": np.zeros(NTRIALS_INIT),
            "trial_num": np.zeros(NTRIALS_INIT, dtype=np.int16),
            "trial_correct": np.zeros(NTRIALS_INIT),
            "reward_amount": np.zeros(NTRIALS_INIT),
            "reward_valve_time": np.zeros(NTRIALS_INIT),
        })


if __name__ == "__main__":
    subject_name = "ZFM-05233"
    session_datetime = "2022-11-24"
    subject_weight = "17.2"
    session_duration = "0:14:10"
    percent_correct = "75%"

    figure = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
    figure.suptitle(f"{subject_name} - {session_datetime}")

    subplot_size = (100, 100)
    ax_bars = plt.subplot2grid(subplot_size, (0, 0), rowspan=100, colspan=40)
    ax_bars.set_title(f"Session Duration: {session_duration}")
    ax_plot1 = plt.subplot2grid(subplot_size, (0, 55), rowspan=25, colspan=25)
    ax_plot1.set_title("plot1")
    ax_performance = plt.subplot2grid(subplot_size, (0, 90), rowspan=25, colspan=10)
    ax_performance.set_title(f"Correct: {percent_correct}")
    ax_plot3 = plt.subplot2grid(subplot_size, (40, 55), rowspan=25, colspan=25)
    ax_plot3.set_title("plot3")
    ax_water = plt.subplot2grid(subplot_size, (40, 90), rowspan=25, colspan=10)
    ax_water.set_title(f"Weight: {subject_weight}gr")
    ax_rig_monitor = plt.subplot2grid(subplot_size, (80, 65), rowspan=20, colspan=30)
    ax_rig_monitor.set_title("Rig Monitor")

    # ax_vars2 = ax_vars.twinx()
    plt.show()
