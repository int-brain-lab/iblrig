import logging
import struct
from dataclasses import dataclass

import numpy as np
from serial_singleton import SerialSingleton

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


class HiFi(SerialSingleton):
    def __init__(self, *args, sampling_rate_hz: int = 192000, attenuation_db: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # self.set_buffer_size(rx_size=1000000, tx_size=1000000)
        self.handshake()
        self._info = self._get_info()
        self._min_attenuation_db = -120 if self.is_hd else -103
        log.debug(f'Connected to Bpod Hifi Module {"HD" if self.is_hd else "SD"} on {self.portstr}')

        self.sampling_rate_hz = sampling_rate_hz
        self.attenuation_db = attenuation_db

    def handshake(self) -> None:
        if not self.query(bytes([243])) == bytes([244]):
            raise OSError(f'Handshake with Bpod Hifi Module on {self.portstr} failed')

    def _get_info(self) -> _HiFiInfo:
        return _HiFiInfo(*self.query(b'I', '<?BBBIII'))

    def _set_info_field(self, field_name: str, format_str: str, op_code: bytes, value: bool | int) -> bool:
        if getattr(self._info, field_name) == value:
            return True
        confirmation = self.query(struct.pack(format_str, op_code, value))
        self._info = self._get_info()
        return confirmation and getattr(self._info, field_name) == value

    @property
    def sampling_rate_hz(self) -> int:
        return self._info.sampling_rate_hz

    @sampling_rate_hz.setter
    def sampling_rate_hz(self, sampling_rate: int) -> None:
        if sampling_rate not in [44100, 48e3, 96e3, 192e3]:
            raise ValueError('Valid values are 44100, 48000, 96000 or 192000')
        if not self._set_info_field('sampling_rate_hz', '<cI', b'S', sampling_rate):
            RuntimeError('Error setting Sampling Rate')
        log.debug(f'Sampling Rate set to {sampling_rate} Hz')

    @property
    def attenuation_db(self) -> float:
        return self._info.digital_attenuation * -0.5

    @attenuation_db.setter
    def attenuation_db(self, attenuation_db: float) -> None:
        if not (self._min_attenuation_db <= attenuation_db <= 0):
            raise ValueError('Valid values are in range -120 - 0')
        if not self._set_info_field('digital_attenuation', '<cB', b'A', round(attenuation_db * -2)):
            raise RuntimeError('Error setting Attenuation')
        log.debug(f'Attenuation set to {self.attenuation_db} dB')

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

    def load(self, index: int, data: np.ndarray[float | int], loop_mode: bool = False, loop_duration: int = 0) -> bool:
        assert isinstance(data, np.ndarray)
        assert data.ndim == 2
        assert data.shape[1] <= 2
        assert 0 <= index < self._info.max_waves

        if data.dtype == float:
            if self._info.bit_depth == 16:
                data = (data * np.iinfo(np.int16).max).astype(np.int16)
            elif self._info.bit_depth == 32:
                data = (data * np.iinfo(np.int32).max).astype(np.int32)
            else:
                raise NotImplementedError
        # else:
        #     if not self._info.bit_depth == data.dtype().nbytes * 8 and data.dtype().:
        #         raise ValueError(f'data must be a ')
        #     elif self._info.bit_depth == 32:
        #         assert data.dtype == np.int32
        #     else:
        #         raise NotImplementedError

        n_samples = data.shape[0]
        if n_samples > self.max_samples_per_waveform:
            raise RuntimeError(
                f'Waveform too long - maximum supported length is {self.max_samples_per_waveform} '
                f'samples ({self.max_samples_per_waveform/self.sampling_rate_hz:.1f}s at '
                f'{self.sampling_rate_hz/1E3:.1f}kHz)'
            )
        is_stereo = data.shape[1] == 2

        self.write('<cB??II', b'L', index, is_stereo, loop_mode, loop_duration, n_samples)
        self.write(data)
        if not self.read() == b'\x01':
            raise Exception
        log.debug(f'Loaded sound to slot #{index}: {n_samples} samples, {"stereo" if is_stereo else "mono"}')

    def play(self, index: int):
        self.write('<cB', b'P', index)
        log.debug(f'Started playback of sound #{index}')

    def push(self) -> bool:
        if not (success := self.query(b'*', '?')[0]):
            raise RuntimeError('Error pushing sounds to playback buffers')
        log.debug('Pushed sounds to playback buffers')
        return success

    def stop(self, index: int | None = None):
        if index is None:
            self.write(b'X')
            log.debug('Playback stopped')
        else:
            self.write('<cB', b'x', index)
            log.debug(f'Playback of sound #{index} stopped')


# from iblrig.sound import make_sound
# from iblutil.util import setup_logger
#
# setup_logger(__name__, level='DEBUG')
# rate = 192000
# hf = HiFi('COM9', sampling_rate_hz=rate, baudrate=115200, timeout=2, attenuation_db=-40)
# sound0 = make_sound(rate=rate, frequency=4000, duration=1)
# # sound0 = np.random.randint(low=np.iinfo(np.int16).min, high=np.iinfo(np.int16).max, size=(1000000, 1), dtype=np.int16)
# hf.load(0, sound0)
# hf.push()
# hf.play(0)
