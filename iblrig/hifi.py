import logging
import struct
from dataclasses import dataclass

# from time import sleep
import numpy as np
from serial_singleton import SerialSingleton, SerialSingletonException

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
    _info = _HiFiInfo

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
        confirmation = self.query(struct.pack(format_str, op_code, value)) == b'\x01'
        self._info = self._get_info()
        return confirmation and getattr(self._info, field_name) == value

    @property
    def sampling_rate_hz(self) -> int:
        return self._info.sampling_rate_hz

    @sampling_rate_hz.setter
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
        assert isinstance(data, np.ndarray)
        assert 1 <= data.ndim <= 2
        assert 0 <= index < self._info.max_waves

        # ensure correct orientation of data
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        if data.shape[1] >= 2 >= data.shape[0] > 0:
            data = data.transpose()

        # convert from float
        if data.dtype == float:
            assert -1 <= data.min() <= 0 <= data.max() <= 1
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
        self.write('<cB??II', b'L', index, is_stereo, loop_mode, loop_duration, n_samples)
        self.write(data)
        if not self.read() == b'\x01':
            raise HiFiException

    def push(self) -> bool:
        log.debug('Pushing waveforms to playback buffers')
        if not (success := self.query(b'*', '?')[0]):
            raise RuntimeError('Error pushing waveforms to playback buffers')
        return success

    def play(self, index: int) -> None:
        log.debug(f'Starting playback of sound #{index}')
        self.write('<cB', b'P', index)

    def stop(self, index: int | None = None):
        if index is None:
            log.debug('Stopping playback')
            self.write(b'X')
        else:
            log.debug(f'Stopping playback of sound #{index}')
            self.write('<cB', b'x', index)


#
#
# from iblutil.util import setup_logger
#
# setup_logger(__name__, level='DEBUG')
#
#
# def upload_and_play_tone(hifi: HiFi,
#                          sf: int = 192000,
#                          f: int = 4000,
#                          d: int = 1,
#                          signal_type: str = 'tone',
#                          channels: str = 'stereo') -> None:
#     t = np.arange(0, int(d * sf)) / sf
#     if signal_type=='tone':
#         wave = np.sin(2 * np.pi * f * t).reshape(1, -1)
#     else:
#         wave = np.random.rand(1, d * sf) * 2 - 1
#
#     if channels=='stereo':  # identical signal on both channels
#         wave = np.concatenate((wave, wave))
#     elif channels=='inverted':  # inverted signal on both channels
#         wave = np.concatenate((wave, -wave))
#     elif channels=='left':
#         wave = np.concatenate((wave, np.zeros(wave.shape)))
#     elif channels=='right':
#         wave = np.concatenate((np.zeros(wave.shape), wave))
#
#     hifi.sampling_rate_hz = sf
#     hifi.load(0, wave)
#     hifi.push()
#     hifi.play(0)
#     sleep(d + 0.1)
#
#
# rate = 192000
# hf = HiFi('COM9', sampling_rate_hz=rate, baudrate=115200, timeout=2, attenuation_db=-80)
#
# for channels in ('stereo', 'inverted', 'mono', 'left', 'right'):
#     for sf in [44100, 192000]:
#         upload_and_play_tone(hf, sf=sf, channels=channels, signal_type='noise')
#         upload_and_play_tone(hf, sf=sf, channels=channels, signal_type='tone')
