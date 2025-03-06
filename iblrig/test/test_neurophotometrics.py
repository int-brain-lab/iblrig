import datetime
import unittest

from iblrig.transfer_experiments import NeurophotometricsCopier


class TestExperimentDescription(unittest.TestCase):
    def test_neurophotometrics_description(self):
        dt = datetime.datetime.fromisoformat('2024-10-11T11:11:00')
        d = NeurophotometricsCopier.neurophotometrics_description(
            rois=['G0', 'G1'],
            locations=['SI', 'VTA'],
            sync_channel=3,
            start_time=dt,
        )
        dexpected = {
            'devices': {
                'neurophotometrics': {
                    'sync_channel': 3,
                    'datetime': '2024-10-11T11:11:00',
                    'collection': 'raw_photometry_data',
                    'fibers': {'G0': {'location': 'SI'}, 'G1': {'location': 'VTA'}},
                    }
                }
            }
        self.assertEqual(dexpected, d)
