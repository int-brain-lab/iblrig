import datetime
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from iblrig.constants import BASE_PATH
from iblrig.neurophotometrics import neurophotometrics_description
from iblrig.path_helper import _load_settings_yaml


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
        settings_dict = _load_settings_yaml(BASE_PATH / 'settings' / 'hardware_settings_template.yaml')
        with patch('iblrig.path_helper._load_settings_yaml', return_value=settings_dict), NamedTemporaryFile() as fp:
            settings_dict['device_neurophotometrics'] = {
                'BONSAI_EXECUTABLE': Path(fp.name),
                'BONSAI_WORKFLOW': Path('devices', 'neurophotometrics', 'FP3002.bonsai'),
                'BONSAI_WORKFLOW_DAQ': Path('devices', 'neurophotometrics', 'FP3002_daq.bonsai'),
                'COM_NEUROPHOTOMETRY': None,
                'FRAMECLOCK_CHANNEL': 'AI7',
            }
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
