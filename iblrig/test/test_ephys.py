import unittest

import numpy as np

import iblrig.ephys


class TestSplitProbes(unittest.TestCase):
    """Tests for iblrig.ephys.split_probes."""

    def test_even_distribution_two_drives(self):
        """4 probes over 2 drives: each drive gets 2 probes in alternating order."""
        result = iblrig.ephys.split_probes(4, ['driveA', 'driveB'])
        np.testing.assert_array_equal(result['driveA'], [0, 2])
        np.testing.assert_array_equal(result['driveB'], [1, 3])

    def test_uneven_distribution_two_drives(self):
        """3 probes over 2 drives: first drive gets 2 probes, second gets 1."""
        result = iblrig.ephys.split_probes(3, ['driveA', 'driveB'])
        np.testing.assert_array_equal(result['driveA'], [0, 2])
        np.testing.assert_array_equal(result['driveB'], [1])

    def test_single_drive(self):
        """All probes assigned to the only drive."""
        result = iblrig.ephys.split_probes(3, ['driveA'])
        np.testing.assert_array_equal(result['driveA'], [0, 1, 2])

    def test_three_drives(self):
        """6 probes over 3 drives: each drive gets exactly 2 probes."""
        result = iblrig.ephys.split_probes(6, ['driveA', 'driveB', 'driveC'])
        np.testing.assert_array_equal(result['driveA'], [0, 3])
        np.testing.assert_array_equal(result['driveB'], [1, 4])
        np.testing.assert_array_equal(result['driveC'], [2, 5])


class TestFinalizeEphysSession(unittest.TestCase):
    def test_neuropixel24_micromanipulator(self):
        probe_dict = {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(probe_dict, 'probe01')
        a = {
            'probe01a': {'x': 2594.2, 'y': -3123.7, 'z': -231.33599999999996, 'phi': 15, 'theta': 15, 'depth': 1250.4, 'roll': 0},
            'probe01b': {
                'x': 2645.963809020504,
                'y': -3316.8851652578132,
                'z': -255.136,
                'phi': 15,
                'theta': 15,
                'depth': 1226.6000000000001,
                'roll': 0,
            },
            'probe01c': {
                'x': 2697.727618041008,
                'y': -3510.070330515627,
                'z': -302.73599999999993,
                'phi': 15,
                'theta': 15,
                'depth': 1179.0,
                'roll': 0,
            },
            'probe01d': {
                'x': 2749.4914270615122,
                'y': -3703.255495773441,
                'z': -350.336,
                'phi': 15,
                'theta': 15,
                'depth': 1131.4,
                'roll': 0,
            },
        }
        assert trajectories == a
