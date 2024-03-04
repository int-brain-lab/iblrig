import datetime
from collections.abc import Sequence

import numpy as np
import scipy
from numpy.polynomial import Polynomial
from pydantic import PositiveFloat, validate_call

from iblrig.hardware import Bpod
from iblrig.pydantic_definitions import HardwareSettingsValve
from pybpodapi.state_machine import StateMachine


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
        if len(self._data) >= 3:
            coef, _ = scipy.optimize.curve_fit(self._fcn, self.open_times_ms, self.volumes_ul, bounds=([-np.inf, 0, 0], np.inf))
        else:
            coef = [np.nan, np.nan, np.nan]
        self._polynomial = Polynomial(coef=coef)

    @validate_call
    def ul2ms(self, volume_ul: PositiveFloat) -> PositiveFloat:
        return max((self._polynomial - volume_ul).roots())

    @validate_call
    def ms2ul(self, volume_ul: PositiveFloat | list[PositiveFloat]) -> PositiveFloat | np.ndarray:
        return self._polynomial(np.array(volume_ul))


class Valve:
    def __init__(self, settings: HardwareSettingsValve):
        self._settings = settings
        self.values = ValveValues(settings.WATER_CALIBRATION_OPEN_TIMES, settings.WATER_CALIBRATION_WEIGHT_PERDROP)

    @property
    def calibration_date(self) -> datetime.date:
        return self._settings.WATER_CALIBRATION_DATE

    @property
    def calibration_range(self) -> tuple[float, float]:
        return self._settings.WATER_CALIBRATION_RANGE

    @property
    def calibration_open_times(self) -> list[float]:
        return self._settings.WATER_CALIBRATION_OPEN_TIMES

    @property
    def calibration_weights(self) -> list[float]:
        return self._settings.WATER_CALIBRATION_WEIGHT_PERDROP

    @property
    def free_reward_time(self) -> float:
        return self._settings.FREE_REWARD_VOLUME_UL


def get_valve_sample(
    bpod: Bpod, open_time_ms: float, close_time_ms: float = 0.1, repetitions: int = 100, valve: str = 'Valve1'
) -> int:
    """Repeatedly open a valve

    Parameters
    ----------
    bpod
    open_time_ms
    close_time_ms
    repetitions
    valve

    Returns
    -------
    int
        The actual number of times the valve was opened. Due to implementation details this number may theoretically
        differ from the requested number of repetitions.
    """
    counter = 0

    def softcode_handler(_):
        nonlocal counter
        counter += 1

    original_softcode_handler = bpod.softcode_handler_function
    bpod.softcode_handler_function = softcode_handler

    sma = StateMachine(bpod)
    sma.set_global_timer(timer_id=1, timer_duration=(open_time_ms + close_time_ms) * repetitions / 1e3)
    sma.add_state(
        state_name='start_timer',
        state_change_conditions={'Tup': 'open'},
        output_actions=[('GlobalTimerTrig', 1)],
    )
    sma.add_state(
        state_name='open',
        state_timer=open_time_ms / 1e3,
        state_change_conditions={'Tup': 'close'},
        output_actions=[(valve, 255), ('SoftCode', 1)],
    )
    sma.add_state(
        state_name='close',
        state_timer=close_time_ms / 1e3,
        state_change_conditions={'Tup': 'open', 'GlobalTimer1_End': 'exit'},
    )
    bpod.send_state_machine(sma)
    bpod.run_state_machine(sma)

    bpod.softcode_handler_function = original_softcode_handler
    return counter
