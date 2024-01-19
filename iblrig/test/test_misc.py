import unittest
import json
import yaml
import tempfile
from pathlib import Path
import shutil
import datetime

import numpy as np
from scipy import stats

from iblrig import misc
from iblrig.misc import online_std

from settings.port_settings import main  # FIXME This is not a module


class TestMisc(unittest.TestCase):
    def test_draw_contrast(self):
        n_draws = 5000
        n_contrasts = 10
        contrast_set = np.linspace(0, 1, n_contrasts)

        def assert_distribution(values: list[int], f_exp: list[float] | None = None) -> None:
            f_obs = np.unique(values, return_counts=True)[1]
            assert stats.chisquare(f_obs, f_exp).pvalue > 0.05

        # uniform distribution
        contrasts = [misc.draw_contrast(contrast_set, 'uniform') for i in range(n_draws)]
        assert_distribution(contrasts)

        # biased distribution
        for p_idx in [0.25, 0.5, 0.75, 1.25]:
            contrasts = [misc.draw_contrast(contrast_set, 'biased', 0, p_idx) for i in range(n_draws)]
            expected = np.ones(n_contrasts)
            expected[0] = p_idx
            expected = expected / expected.sum() * n_draws
            assert_distribution(contrasts, expected)

        self.assertRaises(ValueError, misc.draw_contrast, [], 'incorrect_type')  # assert exception for incorrect type
        self.assertRaises(IndexError, misc.draw_contrast, [0, 1], 'biased', 2)  # assert exception for out-of-range index

    def test_online_std(self):
        n = 41
        b = np.random.rand(n)
        a = b[:-1]
        mu, std = online_std(new_sample=b[-1], new_count=n, old_mean=np.mean(a), old_std=np.std(a))
        np.testing.assert_almost_equal(std, np.std(b))
        np.testing.assert_almost_equal(mu, np.mean(b))


class TestPortSettings(unittest.TestCase):
    """Test settings/port_settings.py."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.v7 = Path(self.temp.name).joinpath('iblrig_params')
        self.v7.mkdir()
        self.v8 = Path(self.temp.name).joinpath('iblrigv8', 'settings')
        self.v8.mkdir(parents=True)
        for template in Path(misc.__file__).parent.parent.glob('settings/*_template.yaml'):
            shutil.copy(template, self.v8 / template.name)
        settings_fixture = Path(misc.__file__).parent.joinpath('test', 'fixtures', 'iblrig_params.json')
        with open(settings_fixture, 'r') as fp:
            self.v7_settings = json.load(fp)
        with open(self.v7 / '.iblrig_params.json', 'w') as fp:
            json.dump(self.v7_settings, fp)

    def test_port_settings(self):
        """Test the porting of settings from V7 to V8."""
        main(self.v7, self.v8)
        hw_settings_path = self.v8 / 'hardware_settings.yaml'
        self.assertTrue(hw_settings_path.exists())
        with open(hw_settings_path, 'r') as fp:
            hw_settings = yaml.safe_load(fp)
        self.assertEqual(hw_settings['device_sound']['OUTPUT'], 'harp')
        expected = {'FREE_REWARD_VOLUME_UL': 1.5,
                    'WATER_CALIBRATION_DATE': datetime.date(2099, 12, 31),
                    'WATER_CALIBRATION_OPEN_TIMES': [50.0, 100.0, 150.0, 200.0],
                    'WATER_CALIBRATION_RANGE': [50.0, 150.0],
                    'WATER_CALIBRATION_WEIGHT_PERDROP': [
                        1.033333333333335, 3.333333333333333, 5.466666666666669, 7.5666666666666655]}
        self.assertDictEqual(hw_settings['device_valve'], expected)
        self.assertEqual(hw_settings['RIG_NAME'], self.v7_settings['NAME'])
        expected = {k: v for k, v in self.v7_settings.items()
                    if k.startswith('SCREEN') or k == 'DISPLAY_IDX'}
        self.assertDictEqual(hw_settings['device_screen'], expected)

        settings_path = self.v8 / 'iblrig_settings.yaml'
        self.assertTrue(settings_path.exists())
        with open(settings_path, 'r') as fp:
            settings = yaml.safe_load(fp)
        self.assertEqual(settings['ALYX_LAB'], 'cortexlab')

        # Test handling of non-standard rig name
        self.v7_settings['NAME'] = '_ibl_foobar_rig_'
        with open(self.v7 / '.iblrig_params.json', 'w') as fp:
            json.dump(self.v7_settings, fp)
        self.assertWarns(Warning, main, self.v7, self.v8)
