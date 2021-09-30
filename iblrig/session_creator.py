#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, March 28th 2019, 7:19:15 pm
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from ibllib.dsp.smooth import rolling_window as smooth

import iblrig.blocks as blocks
import iblrig.misc as misc
import iblrig.path_helper as ph


# EPHYS CHOICE WORLD
def make_ephysCW_pc():
    """make_ephysCW_pc Makes positions, contrasts and block lengths for ephysCW
        Generates ~2000 trias
    :return: pc
    :rtype: [type]
    """
    contrasts = [1.0, 0.25, 0.125, 0.0625, 0.0]
    len_block = [90]
    pos = [-35] * int(len_block[0] / 2) + [35] * int(len_block[0] / 2)
    cont = np.sort(contrasts * 10)[::-1][:-5].tolist()
    prob = [0.5] * len_block[0]
    pc = np.array([pos, cont + cont, prob]).T
    np.random.shuffle(pc)  # only shuffles on the first dimension

    prob_left = 0.8 if blocks.draw_position([-35, 35], 0.5) < 0 else 0.2
    while len(pc) < 2001:
        len_block.append(blocks.get_block_len(60, min_=20, max_=100))
        for x in range(len_block[-1]):
            p = blocks.draw_position([-35, 35], prob_left)
            c = misc.draw_contrast(contrasts, prob_type="uniform")
            pc = np.append(pc, np.array([[p, c, prob_left]]), axis=0)
            # do this in PC space
        prob_left = np.round(np.abs(1 - prob_left), 1)

    return pc, len_block


def make_ephysCW_pcqs(pc):
    qperiod_base = 0.2  # + x, where x~exp(0.35), t ∈ 0.2 <= R <= 0.5
    sphase = []
    qperiod = []
    for i in pc:
        sphase.append(np.random.uniform(0, 2 * math.pi))
        qperiod.append(qperiod_base + misc.texp(factor=0.35, min_=0.2, max_=0.5))
    qs = np.array([qperiod, sphase]).T
    pcqs = np.append(pc, qs, axis=1)
    perm = [0, 1, 3, 4, 2]
    idx = np.empty_like(perm)
    idx[perm] = np.arange(len(perm))
    pcqs[:, idx]
    pcqs[:] = pcqs[:, idx]

    return pcqs


def pre_generate_ephysCW_session_files(
    nsessions, path="./tasks/_iblrig_tasks_ephysChoiceWorld/sessions"
):
    iblrig_path = Path(ph.get_iblrig_folder())
    path = iblrig_path / Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for i in range(nsessions):
        pc, len_block = make_ephysCW_pc()
        pcqs = make_ephysCW_pcqs(pc)
        np.save(path / f"session_{i}_ephys_pcqs.npy", pcqs)
        np.save(path / f"session_{i}_ephys_len_blocks.npy", len_block)


def plot_pcqs(session_num, folder="./tasks/_iblrig_tasks_ephysChoiceWorld/sessions"):
    iblrig_path = Path(ph.get_iblrig_folder())
    folder_path = Path(folder)
    folder = str(iblrig_path / folder_path)
    num = session_num
    pcqs = np.load(folder + f"/pcqs_session_{num}.npy")
    len_block = np.load(folder + f"/pcqs_session_{num}_len_blocks.npy")

    with plt.xkcd(scale=1, length=100, randomness=2):
        f = plt.figure(figsize=(16, 12), dpi=80)
        f.suptitle(f"Session number: {num}")
        ax_position = plt.subplot2grid([2, 2], [0, 0], rowspan=1, colspan=1, fig=f)
        ax_contrast = plt.subplot2grid(
            [2, 2], [0, 1], rowspan=1, colspan=1, fig=f, sharex=ax_position
        )
        ax_qperiod = plt.subplot2grid(
            [2, 2], [1, 0], rowspan=1, colspan=1, fig=f, sharex=ax_position
        )
        ax_sphase = plt.subplot2grid(
            [2, 2], [1, 1], rowspan=1, colspan=1, fig=f, sharex=ax_position
        )

    ax_position.plot(pcqs[:, 0], ".", label="Position", color="b")
    ax_position.plot(smooth(pcqs[:, 0], window_len=20, window="blackman"), alpha=0.5, color="k")

    ax_contrast.plot(pcqs[:, 1] * 100, ".", label="Contrasts")

    ax_qperiod.plot(pcqs[:, 2], ".", label="Quiescent period")

    ax_sphase.plot(pcqs[:, 3], ".", label="Stimulus phase")

    [
        ax.set_ylabel(l)
        for ax, l in zip(
            f.axes,
            ["Position (º)", "Contrasts (%)", "Quiescent period (s)", "Stimulus phase (rad)",],
        )
    ]
    [ax.axvline(x, alpha=0.5) for x in np.cumsum(len_block) for ax in f.axes]
    f.show()
    return pcqs, len_block


# CERTIFICATION
def make_stims_for_certification_pcs(seed_num=None, save=False):
    if seed_num is not None:
        np.random.seed(seed_num)
    iblrig_path = Path(ph.get_iblrig_folder())
    # Generate the position and contrast for the replayed stims
    contrasts = [1.0, 0.5, 0.25, 0.125, 0.0625]

    positions = [-35, 35]
    pc_repeats = 20

    pos = sorted(positions * len(contrasts) * pc_repeats)
    cont = contrasts * pc_repeats * len(positions)

    sphase = [np.random.uniform(0, 2 * math.pi) for x in cont]
    gabors = np.array([[int(p), c, s] for p, c, s in zip(pos, cont, sphase)])

    np.random.shuffle(gabors)
    # Make into strings for saving
    if save:
        fpath = iblrig_path / "visual_stim" / "ephys_certification"
        fpath = fpath / "Extensions" / "certification_stims.csv"
        np.savetxt(fpath, gabors, delimiter=" ", fmt=["%d", "%f", "%f"])

    return gabors


# PASSIVE CHOICE WORLD
def make_stims_for_passiveCW_pcs(seed_num=None, save=False):
    if seed_num is not None:
        np.random.seed(seed_num)
    iblrig_path = Path(ph.get_iblrig_folder())
    # Generate the position and contrast for the replayed stims
    contrasts = [1.0, 0.25, 0.125, 0.0625]
    zero_contrasts = [0.0]

    positions = [-35, 35]
    pc_repeats = 20
    # zero % contrast is added with half the amount of pc_repeats
    zero_repeats = len(positions) * pc_repeats / 2

    pos = sorted(positions * len(contrasts) * pc_repeats)
    cont = contrasts * pc_repeats * len(positions)

    pos.extend(positions * int(zero_repeats / len(positions)))
    cont.extend(zero_contrasts * int(zero_repeats))
    sphase = [np.random.uniform(0, 2 * math.pi) for x in cont]
    gabors = np.array([[int(p), c, s] for p, c, s in zip(pos, cont, sphase)])

    np.random.shuffle(gabors)
    # Make into strings for saving
    if save:
        fpath = iblrig_path / "visual_stim" / "passiveChoiceWorld"
        fpath = fpath / "Extensions" / "passiveCW_stims.csv"
        np.savetxt(fpath, gabors, delimiter=" ", fmt=["%d", "%f", "%f"])

    return gabors


def make_passiveCW_session_delays_ids(seed_num=None):
    if seed_num is not None:
        np.random.seed(seed_num)

    g_len = np.ones((180)) * 0.3
    n_len = np.ones((40)) * 0.5
    t_len = np.ones((40)) * 0.1
    v_len = np.ones((40)) * 0.2

    g_labels = ["G"] * 180
    n_labels = ["N"] * 40
    t_labels = ["T"] * 40
    v_labels = ["V"] * 40

    g_delay_dist = np.random.uniform(0.500, 1.900, len(g_labels))
    n_delay_dist = np.random.uniform(1, 5, len(n_labels))
    t_delay_dist = np.random.uniform(1, 5, len(t_labels))
    v_delay_dist = np.random.uniform(1, 11, len(v_labels))

    # Calculate when they all should happen
    sess_delays_cumsum = np.concatenate(
        [
            np.cumsum(g_delay_dist),
            np.cumsum(n_delay_dist),
            np.cumsum(t_delay_dist),
            np.cumsum(v_delay_dist),
        ]
    )
    sess_labels_out = np.array(g_labels + n_labels + t_labels + v_labels)

    # Sort acording to the when they happen
    srtd_idx = np.argsort(sess_delays_cumsum)
    sess_delays_cumsum = sess_delays_cumsum[srtd_idx]
    sess_labels_out = sess_labels_out[srtd_idx]
    # get the delays between the stims (add the first delay)
    sess_delays_out = np.insert(np.diff(sess_delays_cumsum), 0, sess_delays_cumsum[0])
    tot_dur = (
        np.sum(
            np.sum(g_len) + np.sum(n_len) + np.sum(t_len) + np.sum(v_len) + np.sum(sess_delays_out)
        )
        / 60
    )

    # print(f'Stim IDs: {sess_labels_out}')
    # print(f'Stim delays: {sess_delays_out}')
    print(f"Total duration of stims: {tot_dur} m")

    return sess_delays_out, sess_labels_out


def pre_generate_passiveCW_session_files(
    nsessions, path="./tasks/_iblrig_tasks_ephysChoiceWorld/sessions"
):
    iblrig_path = Path(ph.get_iblrig_folder())
    path = iblrig_path / Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for i in range(nsessions):
        (delays, ids,) = make_passiveCW_session_delays_ids()
        pcs = make_stims_for_passiveCW_pcs()
        np.save(path / f"session_{i}_passive_stimIDs.npy", ids)
        np.save(path / f"session_{i}_passive_stimDelays.npy", delays)
        np.save(path / f"session_{i}_passive_pcs.npy", pcs)
    else:
        (delays, ids,) = make_passiveCW_session_delays_ids()
        pcs = make_stims_for_passiveCW_pcs()
        np.save(path / "session_mock_passive_stimIDs.npy", ids)
        np.save(path / "session_mock_passive_stimDelays.npy", delays)
        np.save(path / "session_mock_passive_pcs.npy", pcs)


def pre_generate_stim_phase(nsessions, path="./tasks/_iblrig_tasks_ephysChoiceWorld/sessions"):
    iblrig_path = Path(ph.get_iblrig_folder())
    path = iblrig_path / Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for i in range(nsessions):
        length = len(np.load(path.joinpath(f"session_{i}_ephys_pcqs.npy")))
        sphase = np.array([np.random.uniform(0, 2 * math.pi) for x in range(length)])
        np.save(path / f"session_{i}_stim_phase.npy", sphase)
    else:
        length = len(np.load(path.joinpath("session_mock_ephys_pcqs.npy")))
        sphase = np.array([np.random.uniform(0, 2 * math.pi) for x in range(length)])
        np.save(path / "session_mock_stim_phase.npy", sphase)


if __name__ == "__main__":
    # np.random.seed(42)
    # pre_generate_stim_phase(12)
    # import seaborn as sns
    # plt.ion()
    # pcqs3, len_block3 = plot_pcqs(3)
    # pcqs9, len_block9 = plot_pcqs(9)
    # sns.distplot(pcqs3[:, 2], vertical=True)
    # sns.jointplot(x=range(len(pcqs9)), y=pcqs9[:, 1])
    # qp = sns.jointplot(x=range(len(pcqs9)),
    #                    y=pcqs9[:, 2], kind='kde', figsize=(16, 12), dpi=80)
    # qp.set_axis_labels(xlabel='Trials', ylabel='Quiescent period (s)')
    # pre_generate_ephysCW_session_filess(1, path='sess')
    # plot_pcqs(0, folder='sess')
    # gabors = make_stims_for_passiveCW_pcs(save=True)
    # pre_generate_passiveCW_session_files(12)
    print(".")
