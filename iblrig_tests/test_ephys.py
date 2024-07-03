import unittest

import iblrig.ephys


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
