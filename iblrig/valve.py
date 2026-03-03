"""Water reward valve calibration and open-time/volume conversion."""

import datetime
import warnings
from collections.abc import Iterable, Sequence
from typing import overload

import numpy as np
import numpy.typing as npt
import scipy
from numpy.polynomial import Polynomial
from pydantic import NonNegativeFloat, PositiveFloat, validate_call

from iblrig.pydantic_definitions import HardwareSettingsValve


class ValveValues:
    """Calibration data and fitted model for a water reward valve.

    Stores paired (open_time, weight) measurements and fits a quadratic
    polynomial via :func:`scipy.optimize.curve_fit` to convert between
    open times (ms) and dispensed volumes (µL).
    """

    _dtype = [('open_times_ms', float), ('weights_g', float)]
    _data: np.ndarray
    _polynomial: Polynomial

    def __init__(self, open_times_ms: Sequence[float], weights_g: Sequence[float]) -> None:
        """Initialise with paired open-time and weight calibration samples.

        Parameters
        ----------
        open_times_ms : sequence of float
            Valve open durations in milliseconds.
        weights_g : sequence of float
            Corresponding water weights in grams (one drop per measurement).
        """
        self.clear_data()
        self.add_samples(open_times_ms, weights_g)

    @staticmethod
    def _fcn(x: npt.NDArray[np.float64], a: float, b: float, c: float) -> npt.NDArray[np.float64]:
        """Quadratic model: ``a + b·x + c·x^2``."""
        return a + b * x + c * np.square(x)

    @validate_call
    def add_samples(self, open_times_ms: Sequence[PositiveFloat], weights_g: Sequence[PositiveFloat]) -> None:
        """Add calibration measurements and refit the model.

        Parameters
        ----------
        open_times_ms : sequence of float
            Valve open durations in milliseconds. All values must be positive.
        weights_g : sequence of float
            Corresponding water weights in grams. All values must be positive.
        """
        incoming = np.rec.fromarrays([open_times_ms, weights_g], dtype=self._dtype)
        self._data = np.append(self._data, incoming)
        self._data = np.sort(self._data)
        self._update_fit()

    def clear_data(self) -> None:
        """Remove all calibration samples and reset the fitted polynomial."""
        self._data = np.empty((0,), dtype=self._dtype)
        self._update_fit()

    @property
    def open_times_ms(self) -> npt.NDArray[np.float64]:
        """Valve open times for all stored calibration samples, in milliseconds."""
        return self._data['open_times_ms']

    @property
    def weights_g(self) -> npt.NDArray[np.float64]:
        """Drop weights for all stored calibration samples, in grams."""
        return self._data['weights_g']

    @property
    def volumes_ul(self) -> npt.NDArray[np.float64]:
        """Dispensed volumes for all stored calibration samples, in microlitres."""
        return self._data['weights_g'] * 1e3

    def _update_fit(self) -> None:
        """Refit the quadratic polynomial to the current calibration data.

        Requires at least two samples. Falls back to ``[nan, nan, nan]``
        coefficients when the fit fails or insufficient data are available.
        """
        c: npt.ArrayLike
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

    @overload
    def ul2ms(self, volume_ul: NonNegativeFloat) -> float: ...

    @overload
    def ul2ms(self, volume_ul: Iterable[NonNegativeFloat]) -> npt.NDArray[np.float64]: ...

    @validate_call
    def ul2ms(self, volume_ul: NonNegativeFloat | Iterable[NonNegativeFloat]) -> float | npt.NDArray[np.float64]:
        """Convert a volume (µL) to the corresponding valve open time (ms).

        Parameters
        ----------
        volume_ul : float or iterable of float
            Target volume(s) in microlitres. Must be non-negative.

        Returns
        -------
        float
            Open time in milliseconds, when *volume_ul* is a scalar.
        numpy.ndarray of float64
            Open times in milliseconds, when *volume_ul* is an iterable.
        """
        if isinstance(volume_ul, Iterable):
            return np.array([self.ul2ms(v) for v in volume_ul])
        elif volume_ul == 0.0:
            return 0.0
        else:
            return max(np.append((self._polynomial - volume_ul).roots(), 0.0))

    @overload
    def ms2ul(self, time_ms: NonNegativeFloat) -> float: ...

    @overload
    def ms2ul(self, time_ms: Iterable[NonNegativeFloat]) -> npt.NDArray[np.float64]: ...

    @validate_call
    def ms2ul(self, time_ms: NonNegativeFloat | Iterable[NonNegativeFloat]) -> float | npt.NDArray[np.float64]:
        """Convert a valve open time (ms) to the corresponding volume (µL).

        Parameters
        ----------
        time_ms : float or iterable of float
            Valve open duration(s) in milliseconds. Must be non-negative.

        Returns
        -------
        float
            Dispensed volume in microlitres, when *time_ms* is a scalar.
        numpy.ndarray of float64
            Dispensed volumes in microlitres, when *time_ms* is an iterable.
        """
        if isinstance(time_ms, Iterable):
            return np.array([self.ms2ul(t) for t in time_ms])
        elif time_ms == 0.0:
            return 0.0
        else:
            return max(np.append(self._polynomial(time_ms), 0.0))


class Valve:
    """High-level interface to a water reward valve.

    Wraps :class:`ValveValues` with hardware settings and provides
    convenience properties for reward volume/timing used during a session.
    """

    def __init__(self, settings: HardwareSettingsValve) -> None:
        """Initialise the valve from hardware settings.

        Parameters
        ----------
        settings : HardwareSettingsValve
            Pydantic model carrying calibration data and valve configuration
            loaded from ``hardware_settings.yaml``.
        """
        self._settings = settings
        volumes_ul = settings.WATER_CALIBRATION_WEIGHT_PERDROP
        weights_g = [volume / 1e3 for volume in volumes_ul]
        self.values = ValveValues(settings.WATER_CALIBRATION_OPEN_TIMES, weights_g)

    @property
    def calibration_date(self) -> datetime.date:
        """Date on which the current calibration was recorded."""
        return self._settings.WATER_CALIBRATION_DATE

    @property
    def is_calibrated(self) -> bool:
        """True if the calibration date is today or in the past."""
        return datetime.date.today() >= self.calibration_date

    @property
    def calibration_range(self) -> list[float]:
        """``[min, max]`` open-time range (ms) used for calibration."""
        return self._settings.WATER_CALIBRATION_RANGE

    @property
    def new_calibration_open_times(self) -> set[float]:
        """Evenly spaced open times (ms) spanning the calibration range."""
        return set(np.linspace(self.calibration_range[0], self.calibration_range[1], self._settings.WATER_CALIBRATION_N))

    @property
    def free_reward_time_sec(self) -> float:
        """Valve open duration in seconds required to dispense one free reward."""
        return self.values.ul2ms(self._settings.FREE_REWARD_VOLUME_UL) / 1000.0

    @property
    def free_reward_volume_ul(self) -> float:
        """Free reward volume in microlitres."""
        return self._settings.FREE_REWARD_VOLUME_UL

    @property
    def settings(self) -> HardwareSettingsValve:
        """Hardware settings updated with the current calibration data."""
        settings = self._settings
        settings.WATER_CALIBRATION_OPEN_TIMES = self.values.open_times_ms.tolist()
        settings.WATER_CALIBRATION_WEIGHT_PERDROP = self.values.volumes_ul.tolist()
        return settings
