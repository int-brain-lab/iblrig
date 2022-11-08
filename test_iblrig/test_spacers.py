import numpy as np
import unittest

from iblrig.spacer import Spacer


class TestSpacer(unittest.TestCase):

    def test_spacer(self):
        spacer = Spacer(dt_start=.02, dt_end=.4, n_pulses=8, tup=.05)
        np.testing.assert_equal(spacer.times.size, 15)
        sig = spacer.generate_template(fs=1000)
        ac = np.correlate(sig, sig, 'full') / np.sum(sig**2)
        # import matplotlib.pyplot as plt
        # plt.plot(ac)
        # plt.show()
        ac[sig.size-100: sig.size + 100] = 0  # remove the main peak
        # the autocorrelation side lobes should be less than 30%
        assert np.max(ac) < .3
