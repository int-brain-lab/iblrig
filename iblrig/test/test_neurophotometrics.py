import datetime
import unittest

from iblrig.neurophotometrics import neurophotometrics_description


class TestExperimentDescription(unittest.TestCase):
    def test_neurophotometrics_description(self):
        dt = datetime.datetime.fromisoformat('2024-10-11T11:11:00')
        d = neurophotometrics_description(
            rois=['Region1G', 'Region2G'], locations=['SI', 'VTA'], sync_channel=3, start_time=dt, sync_mode='bpod'
        )
        dexpected = {
            'devices': {
                'neurophotometrics': {
                    'sync_channel': 3,
                    'datetime': '2024-10-11T11:11:00',
                    'collection': 'raw_photometry_data',
                    'fibers': {'Region1G': {'location': 'SI'}, 'Region2G': {'location': 'VTA'}},
                    'sync_mode': 'bpod',
                }
            }
        }
        self.assertEqual(dexpected, d)
