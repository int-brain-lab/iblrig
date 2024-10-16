import datetime
import warnings
from collections.abc import Iterable, Sequence

import numpy as np
import scipy
from numpy.polynomial import Polynomial
from pydantic import NonNegativeFloat, PositiveFloat, validate_call

from iblrig.pydantic_definitions import HardwareSettingsValve


class ValveValues:
    _dtype = [('open_times_ms', float), ('weights_g', float)]
    _data: np.ndarray
    _polynomial: Polynomial

    def __init__(self, open_times_ms: Sequence[float], weights_g: Sequence[float]):
        self.clear_data()
        self.add_samples(open_times_ms, weights_g)

    @staticmethod
    def _fcn(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        return a + b * x + c * np.square(x)

    @validate_call
    def add_samples(self, open_times_ms: Sequence[PositiveFloat], weights_g: Sequence[PositiveFloat]):
        incoming = np.rec.fromarrays([open_times_ms, weights_g], dtype=self._dtype)
        self._data = np.append(self._data, incoming)
        self._data = np.sort(self._data)
        self._update_fit()

    def clear_data(self):
        self._data = np.empty((0,), dtype=self._dtype)
        self._update_fit()

    @property
    def open_times_ms(self) -> np.ndarray:
        return self._data['open_times_ms']

    @property
    def weights_g(self) -> np.ndarray:
        return self._data['weights_g']

    @property
    def volumes_ul(self) -> np.ndarray:
        return self._data['weights_g'] * 1e3

    def _update_fit(self) -> None:
        if len(self._data) >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                try:
                    c, _ = scipy.optimize.curve_fit(
                        self._fcn, self.open_times_ms, self.volumes_ul, p0=[0, 0, 0], bounds=([-np.inf, 0, 0], np.inf)
                    )
                except RuntimeError:
                    c = [np.nan, np.nan, np.nan]
        else:
            c = [np.nan, np.nan, np.nan]
        self._polynomial = Polynomial(coef=c)

    @validate_call
    def ul2ms(self, volume_ul: NonNegativeFloat | Iterable[NonNegativeFloat]) -> NonNegativeFloat | np.ndarray:
        if isinstance(volume_ul, Iterable):
            return np.array([self.ul2ms(v) for v in volume_ul])
        elif volume_ul == 0.0:
            return 0.0
        else:
            return max(np.append((self._polynomial - volume_ul).roots(), 0.0))

    @validate_call
    def ms2ul(self, time_ms: NonNegativeFloat | Iterable[NonNegativeFloat]) -> NonNegativeFloat | np.ndarray:
        if isinstance(time_ms, Iterable):
            return np.array([self.ms2ul(t) for t in time_ms])
        elif time_ms == 0.0:
            return 0.0
        else:
            return max(np.append(self._polynomial(time_ms), 0.0))


class Valve:
    def __init__(self, settings: HardwareSettingsValve):
        self._settings = settings
        volumes_ul = settings.WATER_CALIBRATION_WEIGHT_PERDROP
        weights_g = [volume / 1e3 for volume in volumes_ul]
        self.values = ValveValues(settings.WATER_CALIBRATION_OPEN_TIMES, weights_g)

    @property
    def calibration_date(self) -> datetime.date:
        return self._settings.WATER_CALIBRATION_DATE

    @property
    def is_calibrated(self) -> bool:
        return datetime.date.today() >= self.calibration_date

    @property
    def calibration_range(self) -> list[float, float]:
        return self._settings.WATER_CALIBRATION_RANGE

    @property
    def new_calibration_open_times(self) -> set[float]:
        return set(np.linspace(self.calibration_range[0], self.calibration_range[1], self._settings.WATER_CALIBRATION_N))

    @property
    def free_reward_time_sec(self) -> float:
        return self.values.ul2ms(self._settings.FREE_REWARD_VOLUME_UL) / 1000.0

    @property
    def free_reward_volume_ul(self) -> float:
        return self._settings.FREE_REWARD_VOLUME_UL

    @property
    def settings(self) -> HardwareSettingsValve:
        settings = self._settings
        settings.WATER_CALIBRATION_OPEN_TIMES = self.values.open_times_ms
        settings.WATER_CALIBRATION_WEIGHT_PERDROP = self.values.volumes_ul
        return settings
