"""Creates sessions, pre-generates stim and ephys sessions."""

from typing import Literal

import numpy as np
import numpy.typing as npt

from iblrig import misc


def draw_position(position_set: npt.ArrayLike, stim_probability_left: float) -> int:
    """Draw a stimulus position by sampling from ``position_set``.

    Parameters
    ----------
    position_set : array-like
        Candidate positions to sample from, ordered ``[left, right]`` (e.g. ``[-35, 35]`` in visual degrees).
    stim_probability_left : float
        Probability of drawing the left position.

    Returns
    -------
    int
        Sampled position value from *position_set*.
    """
    return int(np.random.choice(position_set, p=[stim_probability_left, 1 - stim_probability_left]))


def draw_block_len(factor, min_: int = 20, max_: int = 100) -> int:
    """Draw a block length from a truncated exponential distribution.

    Parameters
    ----------
    factor : float
        Scale parameter of the exponential distribution (inverse of the rate parameter).
    min_ : int, optional
        Minimum block length. Default is 20.
    max_ : int, optional
        Maximum block length. Default is 100.

    Returns
    -------
    int
        Sampled block length in the range [*min_*, *max_*].
    """
    return int(misc.truncated_exponential(scale=factor, min_value=min_, max_value=max_))


def make_ephyscw_pc(prob_type: Literal['biased', 'uniform'] = 'biased') -> tuple[npt.NDArray[np.float64], list[int]]:
    """
    Create positions, contrasts and block lengths for ephysCW.

    Generates a pre-randomised trial table of at least 2001 trials composed of
    alternating blocks with 80/20 left/right stimulus probability. The first
    block is always 90 trials long and fully balanced; subsequent block lengths
    are drawn from a truncated exponential distribution.

    Parameters
    ----------
    prob_type : {'biased', 'uniform'}, optional
        Contrast-sampling scheme for non-zero contrasts. ``'biased'`` draws
        zero-contrast with half the probability of other contrasts;
        ``'uniform'`` draws all contrasts with equal probability.
        Default is ``'biased'``.

    Returns
    -------
    pc : numpy.ndarray, shape (N, 3)
        Trial table with columns ``[position, contrast, prob_left]``. *N* is at least 2001.
    len_block : list of int
        Length of each block, starting with the fixed 90-trial opening block.
    """
    contrasts = [1.0, 0.25, 0.125, 0.0625, 0.0]

    # balanced opening block
    block_lengths = [90]
    pos = [-35] * int(block_lengths[0] / 2) + [35] * int(block_lengths[0] / 2)
    cont = np.sort(contrasts * 10)[::-1][:-5].tolist()
    prob = [0.5] * block_lengths[0]
    pc = np.array([pos, cont + cont, prob]).T
    np.random.shuffle(pc)  # only shuffles on the first dimension

    # remaining blocks
    p_left = 0.8 if draw_position([-35, 35], 0.5) < 0 else 0.2
    while len(pc) < 2001:
        block_lengths.append(draw_block_len(60, min_=20, max_=100))
        for _x in range(block_lengths[-1]):
            p = draw_position([-35, 35], p_left)
            c = misc.draw_contrast(contrasts, probability_type=prob_type)
            pc = np.append(pc, np.array([[p, c, p_left]]), axis=0)
            # do this in PC space
        p_left = np.round(np.abs(1 - p_left), 1)

    return pc, block_lengths
