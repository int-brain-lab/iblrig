"""
The purpose of this module is provide tools to generate and identify spacers.

Spacers are sequences of up and down pulses with a specific, identifiable pattern.
They are generated with a chirp coding to reduce cross-correlaation sidelobes.
They are used to mark the beginning of a behaviour sequence within a session.

Usage:
    spacer = Spacer()
    spacer.add_spacer_states(sma, t, next_state='first_state')
    for i in range(ntrials):
    sma.add_state(
                state_name="first_state",
                state_timer=tup,
                state_change_conditions={"Tup": f"spacer_low_{i:02d}"},
                output_actions=[("BNC1", 255)],  # To FPGA
            )
"""

import numpy as np


class Spacer(object):
    """
    Computes spacer up times using a chirp up and down pattern
    Returns a list of times for the spacer states
    Each time corresponds to an up time of the BNC1 signal

    dt_start: first spacer up time
    dt_end: last spacer up time
    n_pulses: number of spacer up times, one-sided (i.e. 8 means 16 - 1 spacers times)
    tup: duration of the spacer up time
    """
    def __init__(self, dt_start=.02, dt_end=.4, n_pulses=8, tup=.05):
        self.dt_start = dt_start
        self.dt_end = dt_end
        self.n_pulses = n_pulses
        self.tup = tup
        assert np.all(np.diff(self.times) > self.tup), 'Spacers are overlapping'

    def __repr__(self):
        return f"Spacer(dt_start={self.dt_start}, dt_end={self.dt_end}, n_pulses={self.n_pulses}, tup={self.tup})"

    @property
    def times(self, latency=0):
        """
        Computes spacer up times using a chirp up and down pattern
        :return: numpy arrays of times
        """
        # upsweep
        t = np.linspace(self.dt_start, self.dt_end, self.n_pulses) + self.tup
        # downsweep
        t = np.r_[t, np.flipud(t[1:])]
        t = np.cumsum(t)
        return t

    def generate_template(self, fs=1000):
        """
        Generates a spacer voltage template to cross-correlate with a voltage trace
        from a DAQ to detect a voltage trace
        :return:
        """
        t = self.times
        ns = int((t[-1] + self.tup * 10) * fs)
        sig = np.zeros(ns, )
        sig[(t * fs).astype(np.int32)] = 1
        sig[((t + self.tup) * fs).astype(np.int32)] = -1
        sig = np.cumsum(sig)
        return sig

    def add_spacer_states(self, sma=None, next_state="exit"):
        """
        Add spacer states to a state machine
        :param sma: pybpodapi.state_machine.StateMachine object
        :param next_state: name of the state following the spacer states
        :return:
        """
        assert next_state is not None
        t = self.times
        dt = np.diff(t, append=t[-1] + self.tup * 2)
        for i, time in enumerate(t):
            if sma is None:
                print(i, time, dt[i])
                continue
            next_loop = f"spacer_high_{i + 1:02d}" if i < len(t) - 1 else next_state
            sma.add_state(
                state_name=f"spacer_high_{i:02d}",
                state_timer=self.tup,
                state_change_conditions={"Tup": f"spacer_low_{i:02d}"},
                output_actions=[("BNC1", 255)],  # To FPGA
            )
            sma.add_state(
                state_name=f"spacer_low_{i:02d}",
                state_timer=dt[i] - self.tup,
                state_change_conditions={"Tup": next_loop},
                output_actions=[],
            )
