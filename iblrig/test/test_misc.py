import unittest

import numpy as np
from scipy import stats

from iblrig import misc


class TestMisc(unittest.TestCase):
    def test_draw_contrast(self):

        n_draws = 400
        n_contrasts = 10
        contrast_set = np.linspace(0, 1, n_contrasts)

        def assert_distribution(values: list[int], f_exp: list[float] | None = None) -> None:
            f_obs = np.unique(values, return_counts=True)[1]
            assert stats.chisquare(f_obs, f_exp).pvalue > 0.05

        # uniform distribution
        contrasts = [misc.draw_contrast(contrast_set, "uniform") for i in range(n_draws)]
        assert_distribution(contrasts)

        # biased distribution
        for p_idx in [0.25, 0.5, 0.75, 1.25]:
            contrasts = [misc.draw_contrast(contrast_set, "biased", 0, p_idx) for i in range(n_draws)]
            expected = np.ones(n_contrasts)
            expected[0] = p_idx
            expected = expected / expected.sum() * n_draws
            assert_distribution(contrasts, expected)

        self.assertRaises(ValueError, misc.draw_contrast, [], "incorrect_type")  # assert exception for incorrect type
        self.assertRaises(ValueError, misc.draw_contrast, [0, 1], "biased", 2)  # assert exception for out-of-range index
