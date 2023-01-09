import unittest

import iblrig.params as params
import iblrig.iotasks


class TestParamLoading(unittest.TestCase):
    def test_load_pybpod_settings(self):
        settings = iblrig.iotasks.load_pybpod_settings_yaml('pybpod_settings_template.yaml')
        assert len(settings.keys()) == 21
        assert settings['PYBPOD_SUBJECTS'][0] == '_iblrig_fake_mouse'

    def test_load_hardware_settings(self):
        settings = iblrig.iotasks.load_settings_yaml('hardware_settings_template.yaml')
        assert len(settings.keys()) == 6


class TestParams(unittest.TestCase):
    def setUp(self):
        self.incomplete_params_dict = {"NAME": None}

    def test_ensure_all_keys_present(self):
        out = params.ensure_all_keys_present(self.incomplete_params_dict)
        self.assertTrue(out is not None)
        for k in params.EMPTY_BOARD_PARAMS:
            self.assertTrue(k in out)

    def test_create_new_params_dict(self):
        out = params.create_new_params_dict()
        self.assertTrue(out == params.EMPTY_BOARD_PARAMS)

    def test_update_param_key_values(self):
        for k in params.AUTO_UPDATABLE_PARAMS:
            v = params.update_param_key_values(k)
            self.assertTrue(v is not None)

    def test_get_iblrig_version(self):
        from pkg_resources import parse_version

        out = params.get_iblrig_version()
        if "canary" in out:
            return
        self.assertTrue(parse_version(out) >= parse_version("6.4.2"))

    def test_get_pybpod_board_name(self):
        out = params.get_pybpod_board_name()
        self.assertTrue("_iblrig_" in out)
        print(1)

    def test_get_pybpod_board_comport(self):
        out = params.get_pybpod_board_comport()
        self.assertTrue("COM" in out)

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
