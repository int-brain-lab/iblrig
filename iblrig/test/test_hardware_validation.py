import unittest
from unittest import mock
import copy

import requests

import iblrig.hardware_validation
from ibllib.tests import TEST_DB  # noqa
from iblrig.path_helper import _load_settings_yaml
from one.webclient import AlyxClient

VALIDATORS_INIT_KWARGS = dict(
    iblrig_settings=_load_settings_yaml('iblrig_settings_template.yaml'),
    hardware_settings=_load_settings_yaml('hardware_settings_template.yaml'),
)


class DummyValidateHardware(iblrig.hardware_validation.ValidateHardware):
    def _run(self, passes=True):
        if passes:
            return iblrig.hardware_validation.ValidateResult(status='PASS', message='Dummy test passed')
        else:
            return iblrig.hardware_validation.ValidateResult(status='FAIL', message='Dummy test failed')


class TestHardwareValidationBase(unittest.TestCase):
    def test_dummy(self):
        td = DummyValidateHardware(**VALIDATORS_INIT_KWARGS)
        self.assertIsInstance(td.iblrig_settings, dict)
        self.assertIsInstance(td.hardware_settings, dict)
        td.run(passes=True)
        td.run(passes=False)


class TestInstantiateClasses(unittest.TestCase):
    def test_hardware_classes(self):
        iblrig.hardware_validation.ValidateRotaryEncoder(**VALIDATORS_INIT_KWARGS)


class TestAlyxValidation(unittest.TestCase):
    def test_lab_location(self):
        alyx = AlyxClient(**TEST_DB, cache_rest=None)

        kwargs = copy.deepcopy(VALIDATORS_INIT_KWARGS)
        kwargs['hardware_settings']['RIG_NAME'] = '_iblrig_carandinilab_ephys_0'
        v = iblrig.hardware_validation.ValidateAlyxLabLocation(**kwargs)
        result = v.run(alyx)
        self.assertEqual('PASS', result.status)

        # Test failures
        rep = requests.Response()
        with mock.patch('one.webclient.requests.get', return_value=rep) as m:
            m.__name__ = 'get'
            rep.status_code = 404  # When the lab is not found on Alyx the validation should raise
            self.assertRaises(iblrig.hardware_validation.ValidateHardwareException, v.run, alyx)
            rep.status_code = 500  # When Alyx is down for any reason, the failure should not raise
            result = v.run(alyx)
            self.assertEqual('FAIL', result.status)
