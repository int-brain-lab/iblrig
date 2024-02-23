import logging
from dataclasses import dataclass

import numpy as np
from pydantic import validate_call

from iblrig.serial_singleton import SerialSingleton, SerialSingletonException

log = logging.getLogger(__name__)


@dataclass
class _HiFiInfo:
    is_hd: bool
    bit_depth: int
    max_waves: int
    digital_attenuation: int
    sampling_rate_hz: int
    max_seconds_per_waveform: int
    max_envelope_size: int


class HiFiException(SerialSingletonException):
    pass


class HiFi(SerialSingleton):
    @validate_call
    def __init__(self, *args, sampling_rate_hz: int = 192000, attenuation_db: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.handshake():
            raise OSError(f'Handshake with Bpod Hifi Module on {self.portstr} failed')
        self.handshake()
        self._info = self._get_info()
        self._min_attenuation_db = -120 if self.is_hd else -103
        log.debug(f'Connected to Bpod Hifi Module {"HD" if self.is_hd else "SD"} on {self.portstr}')

        self.sampling_rate_hz = sampling_rate_hz
        self.attenuation_db = attenuation_db

    def handshake(self) -> bool:
        return self.query(bytes([243])) == bytes([244])

    def _get_info(self) -> _HiFiInfo:
        return _HiFiInfo(*self.query(query='I', data_specifier='<?BBBIII'))

    def _set_info_field(self, field_name: str, format_str: str, op_code: bytes, value: bool | int) -> bool:
        if getattr(self._info, field_name) == value:
            return True
        self.write_packed(format_str, op_code, value)
        if self.read() == b'\x01':
            setattr(self._info, field_name, value)
        else:
            self._info = self._get_info()
        return getattr(self._info, field_name) == value

    @property
    def sampling_rate_hz(self) -> int:
        return self._info.sampling_rate_hz

    @sampling_rate_hz.setter
    @validate_call
    def sampling_rate_hz(self, sampling_rate: int) -> None:
        log.debug(f'Setting sampling rate to {sampling_rate} Hz')
        if sampling_rate not in [44100, 48e3, 96e3, 192e3]:
            raise ValueError('Valid values are 44100, 48000, 96000 or 192000')
        if not self._set_info_field('sampling_rate_hz', '<cI', b'S', sampling_rate):
            RuntimeError('Error setting Sampling Rate')

    @property
    def attenuation_db(self) -> float:
        return self._info.digital_attenuation * -0.5

    @attenuation_db.setter
    @validate_call
    def attenuation_db(self, attenuation_db: float) -> None:
        log.debug(f'Setting digital attenuation to {self.attenuation_db} dB')
        if not (self._min_attenuation_db <= attenuation_db <= 0):
            raise ValueError('Valid values are in range -120 - 0')
        if not self._set_info_field('digital_attenuation', '<cB', b'A', round(attenuation_db * -2)):
            raise RuntimeError('Error setting Attenuation')

    @property
    def is_hd(self) -> bool:
        return self._info.is_hd

    @property
    def bit_depth(self) -> int:
        return self._info.bit_depth

    @property
    def max_samples_per_waveform(self) -> int:
        return self._info.max_seconds_per_waveform * 192000

    @property
    def max_envelope_samples(self) -> int:
        return self._info.max_envelope_size

    def load(self, index: int, data: np.ndarray[float | int], loop_mode: bool = False, loop_duration: int = 0) -> None:
        assert 1 <= data.ndim <= 2
        assert 0 <= index < self._info.max_waves

        # ensure correct orientation of data
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        if data.shape[1] >= 2 >= data.shape[0] > 0:
            data = data.transpose()

        # convert from float
        if data.dtype == float:
            # assert -1 <= data.min() <= 0 <= data.max() <= 1
            if self._info.bit_depth == 16:
                data = (data * np.iinfo(np.int16).max).astype(np.int16)
            elif self._info.bit_depth == 32:
                data = (data * np.iinfo(np.int32).max).astype(np.int32)
            else:
                raise NotImplementedError

        # get array dimensions
        n_samples, n_channels = data.shape
        if n_samples > self.max_samples_per_waveform:
            raise RuntimeError(
                f'Waveform too long - maximum supported length is {self.max_samples_per_waveform} '
                f'samples ({self.max_samples_per_waveform / self.sampling_rate_hz:.1f}s at '
                f'{self.sampling_rate_hz / 1E3:.1f}kHz)'
            )
        is_stereo = n_channels == 2

        log.debug(f'Loading {n_samples} {"stereo" if is_stereo else "mono"} samples to slot #{index}')
        self.write_packed('<cB??II', b'L', index, is_stereo, loop_mode, loop_duration, n_samples)
        if not self.query(data) == b'\x01':
            raise RuntimeError('Error loading data')

    def push(self) -> bool:
        log.debug('Pushing waveforms to playback buffers')
        if not (success := self.query(b'*') == b'\x01'):
            raise RuntimeError('Error pushing waveforms to playback buffers')
        return success

    def play(self, index: int) -> None:
        log.debug(f'Starting playback of sound #{index}')
        self.write_packed('<cB', b'P', index)

    def stop(self, index: int | None = None):
        if index is None:
            log.debug('Stopping playback')
            self.write(b'X')
        else:
            log.debug(f'Stopping playback of sound #{index}')
            self.write_packed('<cB', b'x', index)
