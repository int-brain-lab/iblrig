import unittest

import iblrig.hardware_validation
from ibllib.tests import TEST_DB  # noqa
from iblrig.path_helper import load_settings_yaml
from one.api import ONE

VALIDATORS_INIT_KWARGS = dict(
    iblrig_settings=load_settings_yaml('iblrig_settings_template.yaml'),
    hardware_settings=load_settings_yaml('hardware_settings_template.yaml')
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
        one = ONE(**TEST_DB, mode='remote')
        import copy
        kwargs = copy.deepcopy(VALIDATORS_INIT_KWARGS)
        kwargs['hardware_settings']['RIG_NAME'] = '_iblrig_carandinilab_ephys_0'
        v = iblrig.hardware_validation.ValidateAlyxLabLocation(**kwargs)
        result = v.run(one)
        assert result.status == 'PASS'
