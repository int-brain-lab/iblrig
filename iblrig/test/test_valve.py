import unittest
from datetime import date

import numpy as np
from pydantic import ValidationError

from iblrig.pydantic_definitions import HardwareSettingsValve
from iblrig.valve import Valve


class TestValve(unittest.TestCase):
    def test_valve(self):
        range_t = range(50, 201, 50)
        range_v = range(4, 21, 5)
        assert len(range_t) == len(range_v)

        settings = HardwareSettingsValve(
            WATER_CALIBRATION_DATE=date.today(),
            WATER_CALIBRATION_RANGE=[min(range_t), max(range_t)],
            WATER_CALIBRATION_N=len(range_t),
            WATER_CALIBRATION_OPEN_TIMES=[t for t in range_t],
            WATER_CALIBRATION_WEIGHT_PERDROP=[v for v in range_v],
            FREE_REWARD_VOLUME_UL=1.5,
        )
        valve = Valve(settings)

        t = np.arange(range_t[0], range_t[-1], 25)
        v = np.arange(range_v[0], range_v[-1], 2.5)
        for i in range(0, len(t)):
            self.assertAlmostEqual(valve.values.ms2ul(t[i]), v[i], places=3)
            self.assertAlmostEqual(valve.values.ul2ms(v[i]), t[i], places=3)
        assert np.allclose(valve.values.ms2ul(t), v)
        assert np.allclose(valve.values.ul2ms(v), t)
        assert valve.values.ul2ms(0) == 0.0
        assert valve.values.ms2ul(0) == 0.0
        assert valve.values.ms2ul(5) == 0.0
        with self.assertRaises(ValidationError):
            valve.values.ms2ul(-1)
        with self.assertRaises(ValidationError):
            valve.values.ms2ul([-1, 1])
        with self.assertRaises(ValidationError):
            valve.values.ul2ms(-1)
        with self.assertRaises(ValidationError):
            valve.values.ul2ms([-2, 1])
