import datetime
import warnings
from collections.abc import Sequence

import numpy as np
import scipy
from numpy.polynomial import Polynomial
from pydantic import PositiveFloat, validate_call

from iblrig.pydantic_definitions import HardwareSettingsValve


class ValveValues:
    _dtype = [('open_times_ms', float), ('weights_g', float)]
    _data: np.ndarray
    _polynomial: Polynomial

    def __init__(self, open_times_ms: Sequence[float], weights_g: Sequence[float]):
        """
        Initialize a ValveValues object.

        Parameters
        ----------
        open_times_ms : Sequence[float]
            Sequence of open times in milliseconds.
        weights_g : Sequence[float]
            Sequence of weights in grams corresponding to the open times.

        Returns
        -------
        None
        """
        self.clear_data()
        self.add_samples(open_times_ms, weights_g)

    @staticmethod
    def _fcn(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        """
        Function for fitting a quadratic curve.

        Parameters
        ----------
        x : np.ndarray
            Input data.
        a : float
            Coefficient for constant term.
        b : float
            Coefficient for lineaer term.
        c : float
            Coefficient for quadratic term.

        Returns
        -------
        np.ndarray
            The result of the polynomial curve fitting.
        """
        return a + b * x + c * np.square(x)

    @validate_call
    def add_samples(self, open_times_ms: Sequence[PositiveFloat], weights_g: Sequence[PositiveFloat]):
        """
        Add samples of open times and weights to the data.

        Parameters
        ----------
        open_times_ms : Sequence[PositiveFloat]
            Sequence of open times in milliseconds.
        weights_g : Sequence[PositiveFloat]
            Sequence of weights in grams corresponding to the open times.

        Returns
        -------
        None
        """
        incoming = np.rec.fromarrays([open_times_ms, weights_g], dtype=self._dtype)
        self._data = np.append(self._data, incoming)
        self._data = np.sort(self._data)
        self._update_fit()

    def clear_data(self) -> None:
        """
        Clear all data stored in the object.

        Returns
        -------
        None
        """
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
        """
        Update the polynomial fit based on the data stored in the object.

        Returns
        -------
        None
        """
        if len(self._data) >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                try:
                    c, _ = scipy.optimize.curve_fit(
                        self._fcn, self.open_times_ms, self.volumes_ul, bounds=([-np.inf, 0, 0], np.inf)
                    )
                except RuntimeError:
                    c = [np.nan, np.nan, np.nan]
        else:
            c = [np.nan, np.nan, np.nan]
        self._polynomial = Polynomial(coef=c)

    @validate_call
    def ul2ms(self, volume_ul: PositiveFloat) -> PositiveFloat:
        """
        Convert from volume to opening time.

        Parameters
        ----------
        volume_ul : PositiveFloat
            Volume in microliters.

        Returns
        -------
        PositiveFloat
            The corresponding opening time in milliseconds.
        """
        return max((self._polynomial - volume_ul).roots())

    @validate_call
    def ms2ul(self, volume_ul: PositiveFloat | list[PositiveFloat]) -> PositiveFloat | np.ndarray:
        """
        Convert from opening time to volume.

        Parameters
        ----------
        volume_ul : PositiveFloat | list[PositiveFloat]
            Opening time in milliseconds or a list of times in milliseconds.

        Returns
        -------
        PositiveFloat | np.ndarray
            The corresponding volume(s) in microliters.
        """
        return self._polynomial(np.array(volume_ul))


class Valve:
    def __init__(self, settings: HardwareSettingsValve):
        """
        Initialize a Valve object.

        Parameters
        ----------
        settings : HardwareSettingsValve
            The hardware settings for the valve.

        Returns
        -------
        None
        """
        self._settings = settings
        volumes_ul = settings.WATER_CALIBRATION_WEIGHT_PERDROP
        weights_g = [volume / 1e3 for volume in volumes_ul]
        self.values = ValveValues(settings.WATER_CALIBRATION_OPEN_TIMES, weights_g)

    @property
    def calibration_date(self) -> datetime.date:
        """
        Get the date of the valve's last calibration.

        Returns
        -------
        datetime.date
            The calibration date.
        """
        return self._settings.WATER_CALIBRATION_DATE

    @property
    def calibration_range(self) -> list[float]:
        """
        Get the calibration range of the valve.

        Returns
        -------
        np.ndarray
            A list containing the minimum and maximum calibration values.
        """
        return self._settings.WATER_CALIBRATION_RANGE

    @property
    def free_reward_time(self) -> float:
        """
        Get the free reward time of the valve.

        Returns
        -------
        float
            The free reward time in seconds.
        """
        return self.values.ul2ms(self._settings.FREE_REWARD_VOLUME_UL) * 1000

    @property
    def settings(self) -> HardwareSettingsValve:
        """
        Get the current hardware settings of the valve.

        Returns
        -------
        HardwareSettingsValve
            The current hardware settings.
        """
        settings = self._settings
        settings.WATER_CALIBRATION_OPEN_TIMES = list(self.values.open_times_ms)
        settings.WATER_CALIBRATION_WEIGHT_PERDROP = list(self.values.volumes_us)
        return settings
