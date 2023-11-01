import unittest

import numpy as np
from scipy import stats

from iblrig import misc


class TestMisc(unittest.TestCase):
    def test_draw_contrast(self):

        contrast_set = np.linspace(0, 1, 11)
        n = 500

        drawn_contrasts = [misc.draw_contrast(contrast_set, "uniform") for i in range(n)]
        frequencies = np.unique(drawn_contrasts, return_counts=True)[1]
        assert stats.chisquare(frequencies).pvalue > 0.05

        for p_idx in np.linspace(0.1, 0.9, 7):
            drawn_contrasts = [misc.draw_contrast(contrast_set, "biased", 0, p_idx) for i in range(n)]
            expected = np.ones(contrast_set.size)
            expected[0] = p_idx
            expected = expected / expected.sum() * n
            frequencies = np.unique(drawn_contrasts, return_counts=True)[1]
            assert stats.chisquare(frequencies, expected).pvalue > 0.05

        self.assertRaises(ValueError, misc.draw_contrast, [], "incorrect_type")  # assert exception for incorrect type
        self.assertRaises(ValueError, misc.draw_contrast, [0, 1], "biased", 2)  # assert exception for out-of-range index
