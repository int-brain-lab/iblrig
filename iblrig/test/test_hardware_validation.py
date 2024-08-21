import unittest

from iblrig.hardware_validation import Result, Status, Validator, get_all_validators, run_all_validators
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings

VALIDATORS_INIT_KWARGS = dict(
    iblrig_settings=load_pydantic_yaml(RigSettings, 'iblrig_settings_template.yaml'),
    hardware_settings=load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml'),
)


class DummyValidateHardware(Validator):
    def _run(self, passes=True):
        if passes:
            yield Result(status=Status.PASS, message='Dummy test passed')
        else:
            yield Result(status=Status.FAIL, message='Dummy test failed')


class TestHardwareValidationBase(unittest.TestCase):
    def test_dummy(self):
        td = DummyValidateHardware(**VALIDATORS_INIT_KWARGS)
        self.assertIsInstance(td.iblrig_settings, RigSettings)
        self.assertIsInstance(td.hardware_settings, HardwareSettings)
        td.run(passes=True)
        td.run(passes=False)


class TestRunAllValidators(unittest.TestCase):
    def test_run_all_validators(self):
        for result in run_all_validators(**VALIDATORS_INIT_KWARGS):
            self.assertIsInstance(result, Result)


# class TestAlyxValidation(unittest.TestCase):
#     def test_lab_location(self):
#         alyx = AlyxClient(**TEST_DB, cache_rest=None)
#
#         kwargs = copy.deepcopy(VALIDATORS_INIT_KWARGS)
#         kwargs['hardware_settings']['RIG_NAME'] = '_iblrig_carandinilab_ephys_0'
#         v = ValidatorAlyxLabLocation(**kwargs)
#         result = v.run(alyx)
#         self.assertEqual(Status.PASS, result.status)
#
#         # Test failures
#         rep = requests.Response()
#         with mock.patch('one.webclient.requests.get', return_value=rep) as m:
#             m.__name__ = 'get'
#             rep.status_code = 404  # When the lab is not found on Alyx the validation should raise
#             self.assertRaises(ValidateHardwareError, v.run, alyx)
#             rep.status_code = 500  # When Alyx is down for any reason, the failure should not raise
#             result = v.run(alyx)
#             self.assertEqual(Status.FAIL, result.status)
