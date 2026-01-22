import datetime
import unittest

import numpy as np
import pandas as pd

import ibllib.time
import iblrig.ephys
from ibllib.tests import TEST_DB
from one.api import ONE


class TestMicromanipulatorCompute(unittest.TestCase):
    def setUp(self):
        self.actual = {
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
        self.actual = pd.DataFrame(self.actual)
        # the test use custom spacings, those are (0, 250, 500, 750) by default for NP2.4 probes
        self.shanks_spacings_um = (0, 200, 400, 600)

    def test_neuropixel24_micromanipulator(self):
        probe_dict = {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(
            probe_dict, 'probe01', shank_spacings_um=self.shanks_spacings_um)
        np.testing.assert_array_almost_equal(self.actual.to_numpy(), pd.DataFrame(trajectories).sort_index(axis=1).to_numpy())

    def test_neuropixel24_micromanipulator_reversed(self):
        probe_dict = {
            'x': 2749.4914270615122,
            'y': -3703.255495773441,
            'z': -350.336,
            'phi': 15,
            'theta': 15,
            'depth': 1131.4,
            'roll': 0,
        }
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(
            probe_dict, 'probe01', pivot_shank='d', shank_spacings_um=self.shanks_spacings_um)
        np.testing.assert_array_almost_equal(self.actual.to_numpy(), pd.DataFrame(trajectories).sort_index(axis=1).to_numpy())


class TestMicromanipulatorRegister2Alyx(unittest.TestCase):
    def setUp(self):
        self.one = ONE(**TEST_DB)
        ses_dict = {
            'subject': 'algernon',
            'start_time': ibllib.time.date2isostr(datetime.datetime.now()),
            'number': 1,
            'users': ['test_user'],
        }
        self.rest_session = self.one.alyx.rest('sessions', 'create', data=ses_dict)

    def tearDown(self):
        self.one.alyx.rest('sessions', 'delete', id=self.rest_session['id'])

    def test_probe_and_trajectories_creation(self):
        probe_dict = {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(probe_dict, 'probe01')
        iblrig.ephys.register_micromanipulator_coordinates(
            alyx=self.one.alyx, trajectories=trajectories, eid=self.rest_session['id']
        )
        # do it twice to make sure both the get and create cases work
        iblrig.ephys.register_micromanipulator_coordinates(
            alyx=self.one.alyx, trajectories=trajectories, eid=self.rest_session['id']
        )
