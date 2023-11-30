import unittest

import iblrig.hardware_validation
from iblrig.path_helper import load_settings_yaml


class DummyTestHardware(iblrig.hardware_validation.TestHardware):

    def _run(self, passes=True):
        if passes:
            return iblrig.hardware_validation.TestResult(status='PASS', message='Dummy test passed')
        else:
            return iblrig.hardware_validation.TestResult(status='FAIL', message='Dummy test failed')


class TestHardwareValidationBase(unittest.TestCase):
    def test_dummy(self):
        td = DummyTestHardware(
            iblrig_settings=load_settings_yaml('iblrig_settings_template.yaml'),
            hardware_settings=load_settings_yaml('hardware_settings_template.yaml')
        )
        self.assertIsInstance(td.iblrig_settings, dict)
        self.assertIsInstance(td.hardware_settings, dict)
        td.run(passes=True)
        td.run(passes=False)


class TestInstantiateClasses(unittest.TestCase):

    def test_hardware_classes(self):
        iblrig.hardware_validation.TestRotaryEncoder()
