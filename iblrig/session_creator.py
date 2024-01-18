"""
Creates sessions, pre-generates stim and ephys sessions
"""
import math

import numpy as np

from iblrig import misc


def draw_position(position_set, stim_probability_left) -> int:
    return int(np.random.choice(position_set, p=[stim_probability_left, 1 - stim_probability_left]))


def draw_block_len(factor, min_=20, max_=100):
    return int(misc.truncated_exponential(scale=factor, min_value=min_, max_value=max_))


# EPHYS CHOICE WORLD
def make_ephysCW_pc(prob_type='biased'):
    """make_ephysCW_pc Makes positions, contrasts and block lengths for ephysCW
        Generates ~2000 trias
    :prob_type: (str) 'biased': 0 contrast half has likely to be drawn, 'uniform': 0 contrast as
    likely as other contrasts
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

    prob_left = 0.8 if draw_position([-35, 35], 0.5) < 0 else 0.2
    while len(pc) < 2001:
        len_block.append(draw_block_len(60, min_=20, max_=100))
        for _x in range(len_block[-1]):
            p = draw_position([-35, 35], prob_left)
            c = misc.draw_contrast(contrasts, probability_type=prob_type)
            pc = np.append(pc, np.array([[p, c, prob_left]]), axis=0)
            # do this in PC space
        prob_left = np.round(np.abs(1 - prob_left), 1)

    return pc, len_block


def make_ephysCW_pcqs(pc):
    qperiod_base = 0.2  # + x, where x~exp(0.35), t ∈ 0.2 <= R <= 0.5
    sphase = []
    qperiod = []
    for _i in pc:
        sphase.append(np.random.uniform(0, 2 * math.pi))
        qperiod.append(qperiod_base + misc.truncated_exponential(scale=0.35, min_value=0.2, max_value=0.5))
    qs = np.array([qperiod, sphase]).T
    pcqs = np.append(pc, qs, axis=1)
    perm = [0, 1, 3, 4, 2]
    idx = np.empty_like(perm)
    idx[perm] = np.arange(len(perm))
    pcqs[:, idx]
    pcqs[:] = pcqs[:, idx]

    return pcqs


# PASSIVE CHOICE WORLD
def make_stims_for_passiveCW_pcs(seed_num=None):  # XXX
    if seed_num is not None:
        np.random.seed(seed_num)
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
    # if save:
    #     fpath = iblrig_path / "visual_stim" / "passiveChoiceWorld"
    #     fpath = fpath / "Extensions" / "passiveCW_stims.csv"
    #     np.savetxt(fpath, gabors, delimiter=" ", fmt=["%d", "%f", "%f"])

    return gabors


def make_passiveCW_session_delays_ids(seed_num=None):  # XXX
    if seed_num is not None:
        np.random.seed(seed_num)

    g_len = np.ones(180) * 0.3
    n_len = np.ones(40) * 0.5
    t_len = np.ones(40) * 0.1
    v_len = np.ones(40) * 0.2

    g_labels = ['G'] * 180
    n_labels = ['N'] * 40
    t_labels = ['T'] * 40
    v_labels = ['V'] * 40

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
    tot_dur = np.sum(np.sum(g_len) + np.sum(n_len) + np.sum(t_len) + np.sum(v_len) + np.sum(sess_delays_out)) / 60

    # print(f'Stim IDs: {sess_labels_out}')
    # print(f'Stim delays: {sess_delays_out}')
    print(f'Total duration of stims: {tot_dur} m')

    return sess_delays_out, sess_labels_out
