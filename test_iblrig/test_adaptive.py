import unittest

from brainbox.core import Bunch

import iblrig.adaptive as adaptive


class TestsAdaptive(unittest.TestCase):
    def setUp(self):
        self.sph = Bunch(
            {
                "ADAPTIVE_REWARD": True,
                "REWARD_AMOUNT": 3,
                "AR_INIT_VALUE": 3.0,
                "AR_MIN_VALUE": 1.5,
                "AR_STEP": 0.1,
                "AR_CRIT": 3.0,
                "AR_MAX_VALUE": 3.0,
                "AUTOMATIC_CALIBRATION": True,
                "LAST_SETTINGS_DATA": None,
                "LAST_TRIAL_DATA": None,
                "LATEST_WATER_CALIBRATION_FILE": "",
                "LATEST_WATER_CALIB_RANGE_FILE": "",
                "CALIB_FUNC": "",
                "CALIB_FUNC_RANGE": "",
                "ADAPTIVE_GAIN": "",
                "STIM_GAIN": "",
                "AG_MIN_VALUE": "",
                "AG_INIT_VALUE": "",
            }
        )

    def testInitRewardAmount(self):
        out = adaptive.init_reward_amount(self.sph)
        self.assertTrue(out == 3.0)
        sph = self.sph.copy()
        # Test return previous reward amount
        sph["LAST_TRIAL_DATA"] = {"trial_num": 199, "reward_amount": 999}
        sph["LAST_SETTINGS_DATA"] = {}
        out = adaptive.init_reward_amount(sph)
        self.assertTrue(out == 999)
        # Test return reduction of amount
        sph["LAST_TRIAL_DATA"] = {"trial_num": 200, "reward_amount": 999}
        out = adaptive.init_reward_amount(sph)
        self.assertTrue(out == 999 - sph.AR_STEP)

    def testAppendFlagFile(self):
        pass

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
