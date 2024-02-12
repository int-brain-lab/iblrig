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
        self.handshake()

        self._info = self._get_info()
        self.sampling_rate_hz = sampling_rate_hz
        self.attenuation_db = attenuation_db

        log.debug(f'Connected to BpodHifi {"HD" if self.is_hd else "SD"} on port {self.portstr}.')

    def handshake(self, raise_on_fail: bool = True) -> bool:
        self.flushInput()
        status = self.query(bytes([243])) == bytes([244])
        if not status and raise_on_fail:
            raise OSError(f'Device on {self.portstr} is not a Bpod HiFi Module')
        return status

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
            raise ValueError('Valid values are 44100, 48000, 96000 or 192000.')
        if not self._set_info_field('sampling_rate', '<cI', b'S', sampling_rate):
            RuntimeError('Error setting Sampling Rate')
        log.debug(f'Sampling Rate set to {sampling_rate} Hz.')

    @property
    def attenuation_db(self) -> float:
        return self._info.digital_attenuation * -0.5

    @attenuation_db.setter
    def attenuation_db(self, attenuation_db: float) -> None:
        if not (-120 <= attenuation_db <= 0):
            raise ValueError('Valid values are in range -120 - 0.')
        if not self._set_info_field('digital_attenuation', '<cB', b'A', round(attenuation_db * -2)):
            raise RuntimeError('Error setting Attenuation')
        log.debug(f'Attenuation set to {self.attenuation_db} dB.')

    @property
    def is_hd(self) -> bool:
        return self._info.is_hd

    @property
    def bit_depth(self) -> int:
        return self._info.bit_depth

    def load(self, index: int, data: np.ndarray) -> bool:
        pass

    def play(self, index: int):
        self.write([b'P', index], '<cB')

    def stop(self, index: int | None = None):
        if index is None:
            self.write('X')
        else:
            self.write(struct.pack('<cB', b'x', index))
