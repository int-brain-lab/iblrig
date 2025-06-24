import datetime
import unittest

from iblrig.neurophotometrics import neurophotometrics_description


class TestExperimentDescription(unittest.TestCase):
    def test_neurophotometrics_description(self):
        # tests the generation of the acquisition description
        dt = datetime.datetime.fromisoformat('2024-10-11T11:11:00')

        # for bpod based sync
        d = neurophotometrics_description(
            rois=['G0', 'G1'], locations=['SI', 'VTA'], sync_channel=1, start_time=dt, sync_mode='bpod'
        )
        dexpected = {
            'devices': {
                'neurophotometrics': {
                    'sync_channel': 1,
                    'datetime': '2024-10-11T11:11:00',
                    'collection': 'raw_photometry_data',
                    'fibers': {'G0': {'location': 'SI'}, 'G1': {'location': 'VTA'}},
                    'sync_mode': 'bpod',
                }
            }
        }
        self.assertDictEqual(dexpected, d)

        # for daqami sync
        d = neurophotometrics_description(
            rois=['G0', 'G1'], locations=['SI', 'VTA'], sync_channel=1, start_time=dt, sync_mode='daqami'
        )
        dexpected = {
            'devices': {
                'neurophotometrics': {
                    'sync_channel': 1,
                    'datetime': '2024-10-11T11:11:00',
                    'collection': 'raw_photometry_data',
                    'fibers': {'G0': {'location': 'SI'}, 'G1': {'location': 'VTA'}},
                    'sync_mode': 'daqami',
                    'sync_metadata': {
                        'acquisition_software': 'daqami',
                        'collection': 'raw_photometry_data',
                        'frameclock_channel': 'AI7',
                    },
                }
            }
        }
        self.assertDictEqual(dexpected, d)
