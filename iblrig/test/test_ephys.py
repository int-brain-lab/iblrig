import unittest

import pandas as pd
import numpy as np

import iblrig.ephys


class TestFinalizeEphysSession(unittest.TestCase):

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

    def test_neuropixel24_micromanipulator(self):
        probe_dict = {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(probe_dict, 'probe01')
        np.testing.assert_array_almost_equal(self.actual.to_numpy(), pd.DataFrame(trajectories).sort_index(axis=1).to_numpy())

    def test_neuropixel24_micromanipulator_reversed(self):
        probe_dict = {'x': 2749.4914270615122, 'y': -3703.255495773441, 'z': -350.336, 'phi': 15, 'theta': 15, 'depth': 1131.4, 'roll': 0}
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(probe_dict, 'probe01', pivot_shank='d')
        np.testing.assert_array_almost_equal(self.actual.to_numpy(), pd.DataFrame(trajectories).sort_index(axis=1).to_numpy())

    def test_probe_creation(self):
        pass

# %%
from pathlib import Path

import iblrig.ephys
from ibllib.ephys.spikes import create_insertion
from one.api import ONE
from one.webclient import no_cache as no_cache_context
one = ONE(base_url='https://test.alyx.internationalbrainlab.org')
probe_dict = {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(probe_dict, 'probe01')
#
# from iblrig.test.base import TASK_KWARGS
# from iblrig.test.test_base_tasks import EmptyHardwareSession
# TASK_KWARGS['subject'] = 'algernon'
# task = EmptyHardwareSession(one=one, **TASK_KWARGS)
# task.register_to_alyx()


import ibllib.time
import datetime
ses_dict = {
    'subject': 'algernon',
    'start_time': ibllib.time.date2isostr(datetime.datetime.now()),
    'number': 1,
    'users': ['test_user']}
ses = one.alyx.rest('sessions', 'create', data=ses_dict)


# is it ok to add another test hitting the alyx test database ?
# %%
import neuropixel
import ibllib.pipes.histology
neuropixel.trace_header(version=2, nshank=4)
from iblutil.util import Bunch
metadata = Bunch({'neuropixelVersion': 'NP2.4', 'fileName': '/path/to/file.bin', 'serial': 813867658})
rest_insertions = {}
with no_cache_context(one.alyx):
    traj_extra = {}
    for pname, traj in trajectories.items():
        _, rest_insertion = create_insertion(one, metadata, pname, eid=ses['id'])
        traj_extra['probe_insertion'] = rest_insertion['id']
        traj_extra['chronic_insertion'] = None
        traj_extra['provenance'] =  'Micro-manipulator'
        traj_extra['coordinate_system'] = 'Needles-Allen'
        rest_trajectory = one.alyx.rest('trajectories', 'list', probe_insertion=rest_insertion['id'], provenance='Micro-manipulator')
        if len(rest_trajectory) == 0:
            rest_trajectory = one.alyx.rest('trajectories', 'create', data=traj | traj_extra)
        else:
            rest_trajectory = one.alyx.rest('trajectories', 'update', id=rest_trajectory[0]['id'], data=traj | traj_extra)

