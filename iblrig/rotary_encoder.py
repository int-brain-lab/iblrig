import logging
import struct
from typing import Literal, overload

import numpy as np
from numpy.typing import NDArray
from serial import SerialException

from bpod_core.com import ExtendedSerial

log = logging.getLogger(__name__)

DTYPE_LOGGING = np.dtype([('time', 'timedelta64[us]'), ('degrees', 'f8')])


class RotaryEncoderModule:
    _name: str = 'Rotary Encoder Module'
    _is_sd_logging: bool = False
    _encoder_resolution: int = 1024
    _clock_multiplier: int
    _factor_tick_to_deg: float
    _factor_deg_to_tick: float
    _wrap_mode: Literal['bipolar', 'unipolar'] = 'bipolar'
    _wrap_point_tics: int
    _thresholds: list[float] = []
    _max_thresholds: int = 8
    _event_transmission: bool = False

    def __init__(self, port: str, encoder_resolution: int = 1024, reset_to_defaults: bool = True):
        """Create a RotaryEncoderModule instance and open the connection.

        Parameters
        ----------
        port : str
            Serial port name (e.g., ``'/dev/ttyACM0'`` or ``'COM5'``).
        encoder_resolution : int, optional
            The incremental encoder's resolution in pulses per revolution. Defaults to 1024.
        reset_to_defaults : bool, optional
            Whether to reset the Rotary Encoder Module to default settings. Defaults to True.

        Raises
        ------
        SerialException
            If the port cannot be opened during the probe step.
        ValueError
            If the device on the given port does not appear to be a Rotary
            Encoder Module.
        """
        # handshake / identify hardware version
        self._hardware_version = self.probe(port)

        # rotary encoder module v1 uses X1 encoding, v2 uses X4 encoding
        self._clock_multiplier = 1 if self._hardware_version == 1 else 4

        # set encoder resolution
        self.encoder_resolution = encoder_resolution

        # initialize serial object and set port
        # implemented that awkwardly to get logging from self.open()
        self._serial = ExtendedSerial()
        self._serial.port = port
        self.open()

        # reset to default settings
        if reset_to_defaults:
            self.reset()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        self.close()

    @staticmethod
    @overload
    def probe(port: str, raise_exceptions: Literal[True] = True) -> int: ...

    @staticmethod
    @overload
    def probe(port: str, raise_exceptions: Literal[False]) -> int | None: ...

    @staticmethod
    def probe(port: str, raise_exceptions: bool = True):
        """
        Probe for a Rotary Encoder Module on the specified port.

        Parameters
        ----------
        port : str
            The port to probe.
        raise_exceptions : bool, optional
            Whether to raise a ValueError when device does not appear to be a rotary encoder. Defaults to True.

        Returns
        -------
        int or None
            The hardware version of the Rotary Encoder Module.
            Will return None if the device does not appear to be a Rotary Encoder Module and `raise_exceptions` is False.

        Raises
        ------
        SerialException
            If the port cannot be opened.
        ValueError
            If the device does not appear to be a Rotary Encoder Module and `raise_exceptions` is True.
        """
        hardware_version = None
        try:
            with ExtendedSerial(port, timeout=0.1) as s:
                s.reset_input_buffer()
                reply = s.query(b'CI\xfa', 2)
            if len(reply) == 0:
                raise TimeoutError(f'Device on {port} did not respond to query within {s.timeout} seconds.')
            match reply:
                case b'\xd9\x01':
                    hardware_version = 1
                case b'\xd9\x00':
                    hardware_version = 2
                case _:
                    raise NotImplementedError(f'Unexpected response from device on {port}: {reply!r}')
        except SerialException as e:
            if 'could not open port' in str(e):
                raise SerialException(f'Could not connect to device on {port}. Is the device connected?') from e
            else:
                raise
        except (TimeoutError, NotImplementedError) as e:
            if raise_exceptions:
                raise ValueError(f'Device on {port} does not appear to be a Rotary Encoder Module.') from e
        return hardware_version

    def _degrees_to_tics(self, degrees: float) -> int:
        """Convert degrees to tics."""
        return round(degrees * self._factor_deg_to_tick)

    def _tics_to_degrees(self, tics: int) -> float:
        """Convert tics to degrees."""
        return tics * self._factor_tick_to_deg

    @property
    def _tics(self) -> int:
        return self._serial.query_struct(b'Q', '<h')[0]

    @_tics.setter
    def _tics(self, value: int) -> None:
        self._serial.write_struct('<ch', b'P', value)
        if not self._serial.verify(b''):
            raise RuntimeError(f'Failed to set position to {value} tics')

    def _reset_data_streams(self):
        self._serial.write(b'X')
        self._is_sd_logging = False
        log.debug('All data streams reset')

    def reset(self):
        """Reset Rotary Encoder Module to default settings."""
        self.wrap_point = 180.0
        self.thresholds = [-40.0, 40.0]
        self.wrap_mode = 'bipolar'
        self.event_transmission = False
        # obj.moduleOutputStream = 'off';
        if self._hardware_version == 1:
            self.set_stream_prefix('M')

    @property
    def hardware_version(self) -> int:
        """Hardware version of the Rotary Encoder Module."""
        return self._hardware_version

    @property
    def clock_multiplier(self) -> int:
        """Clock multiplier of the Rotary Encoder Module."""
        return self._clock_multiplier

    @property
    def encoder_resolution(self) -> int:
        """Resolution of the Incremental Encoder in pulses per revolution."""
        return self._encoder_resolution

    @encoder_resolution.setter
    def encoder_resolution(self, value: int) -> None:
        if value <= 0:
            raise ValueError('Encoder resolution must be a positive integer.')
        self._encoder_resolution = int(value)
        self._factor_tick_to_deg = 360.0 / (self._encoder_resolution * self._clock_multiplier)
        self._factor_deg_to_tick = (self._encoder_resolution * self._clock_multiplier) / 360.0

    @property
    def port(self) -> str | None:
        """Port name of the Rotary Encoder Module."""
        return self._serial.port

    def open(self) -> None:
        """Open serial connection to the Rotary Encoder Module."""
        if not self._serial.is_open:
            log.debug('Opening serial connection to %s v%d on %s', self._name, self._hardware_version, self.port)
            self._serial.open()

    def close(self) -> None:
        """Close serial connection to the Rotary Encoder Module."""
        self.sd_logging = False
        if hasattr(self, '_serial') and self._serial.is_open:
            log.debug('Closing serial connection to %s v%d on %s', self._name, self._hardware_version, self.port)
            self._serial.close()

    @property
    def wrap_point(self) -> float:
        """Get or set the wrap point in degrees."""
        return self._tics_to_degrees(self._wrap_point_tics)

    @wrap_point.setter
    def wrap_point(self, degrees: float) -> None:
        tics = self._degrees_to_tics(abs(degrees))
        query = struct.pack('<cI', b'W', tics)
        if self._serial.verify(query):
            self._wrap_point_tics = tics
            log.debug('Setting wrap point to %0.1f°', self.wrap_point)
        else:
            raise RuntimeError('Failed to set wrap point')

    @property
    def thresholds(self) -> list[float]:
        """List of thresholds in degrees."""
        return self._thresholds

    @thresholds.setter
    def thresholds(self, degrees: list[float]) -> None:
        if any(abs(threshold) > self.wrap_point for threshold in degrees):
            raise ValueError(f'Threshold values cannot exceed the current wrap point of {self.wrap_point}°.')
        if (n_thresholds := len(degrees)) > 8:
            raise ValueError(f'A maximum of {self._max_thresholds} thresholds can be set.')
        tics = [self._degrees_to_tics(thresh) for thresh in degrees]
        degrees = [self._tics_to_degrees(tick) for tick in tics]
        query = struct.pack(f'<cB{n_thresholds}h', b'T', n_thresholds, *tics)
        if self._serial.verify(query):
            self._thresholds = degrees
            log.debug('Setting thresholds to %s', ', '.join([f'{x:0.1f}°' for x in degrees]))
        else:
            raise RuntimeError('Failed to set thresholds')

    @property
    def sd_logging(self) -> bool:
        """The state of SD card logging."""
        return self._is_sd_logging

    @sd_logging.setter
    def sd_logging(self, enable_logging: bool) -> None:
        if enable_logging == self._is_sd_logging:
            return
        if self.hardware_version != 1:
            raise RuntimeError(f'SD card logging is not supported on {self._name} v{self.hardware_version}')
        if enable_logging:
            self._serial.write(b'L')
            log.debug('Logging enabled')
        else:
            self._serial.write(b'F')
            log.debug('Logging disabled')
        self._is_sd_logging = bool(enable_logging)

    @property
    def degrees(self) -> float:
        """Current encoder position in degrees."""
        return self._tics_to_degrees(self._tics)

    @degrees.setter
    def degrees(self, degrees: float):
        try:
            self._tics = self._degrees_to_tics(degrees)
            log.debug('Setting encoder position to %0.1f°', self.degrees)
        except RuntimeError as e:
            raise RuntimeError(f'Failed to set encoder position to {degrees:0.1f}') from e

    def zero(self) -> None:
        """Reset current encoder position to zero."""
        log.debug('Resetting encoder position to 0°.')
        self._serial.write(b'Z')

    def enable_sd_logging(self):
        """
        Enables logging to the SD Card.

        Only supported for hardware version 1.

        Raises
        ------
        RuntimeError
            If the hardware version is not 1.
        """
        self.sd_logging = True

    def disable_sd_logging(self):
        """
        Disables logging to the SD Card.

        Only supported for hardware version 1.

        Raises
        ------
        RuntimeError
            If the hardware version is not 1.
        """
        self.sd_logging = False

    def get_logged_data(self) -> NDArray[np.void]:
        """Retrieve logged data from the SD card.

        Returns
        -------
        numpy.ndarray
            Structured NumPy array with one element per logged sample.
            Each element has the following fields:

            - ``time`` :class:`numpy.timedelta64` with unit ``us``
            - ``degrees`` :class:`numpy.float64`
        """
        if self.hardware_version != 1:
            raise RuntimeError(f'SD card logging is not supported on {self._name} v{self.hardware_version}')

        self.sd_logging = False  # stop logging before retrieving data

        # prepare output array
        n_records = self._serial.query_struct(b'R', '<I')[0]
        out = np.empty(n_records, dtype=DTYPE_LOGGING)
        if n_records == 0:
            return out

        # retrieve data from rotary encoder module and parse into structured array
        buffer = self._serial.read(n_records * 8)
        dtype = np.dtype([('tics', np.int32), ('time', np.uint32)])
        raw_data = np.frombuffer(buffer, dtype=dtype)
        out['time'] = raw_data['time'].astype('timedelta64[us]')
        np.multiply(raw_data['tics'], self._factor_tick_to_deg, out=out['degrees'])

        # Correct rollover in 32-bit microsecond timer
        rollover_indices = np.where(np.diff(raw_data['time']) < 0)[0] + 1
        if rollover_indices.size:
            for i, start in enumerate(rollover_indices):
                end = rollover_indices[i + 1] if i + 1 < len(rollover_indices) else n_records
                delta = np.timedelta64((i + 1) * 2**32, 'us')
                out['time'][start:end] += delta

        return out

    def set_stream_prefix(self, prefix: str | bytes = b'M') -> None:
        """
        Set the stream prefix.

        Parameters
        ----------
        prefix : str or bytes, optional
            A single character or byte to be used as the stream prefix.

        Raises
        ------
        ValueError
            If the prefix is not a single character or byte.
        RuntimeError
            If the hardware version is not 1 or if setting the prefix fails.
        """
        # Raise exception if not version 1
        if self.hardware_version != 1:
            raise RuntimeError('Setting of stream prefix is only supported for %s v1', self._name)

        # validate prefix and convert to bytes if necessary
        match prefix:
            case str():
                prefix = prefix.encode()
            case bytes():
                pass
            case _:
                raise ValueError('Stream prefix must be of type str or bytes.')
        if len(prefix) > 1:
            raise ValueError('Stream prefix must have a length of 1.')

        # send command and read response
        if self._serial.verify(b'I' + prefix):
            log.debug('Setting stream prefix to %s', prefix)
        else:
            raise RuntimeError('Failed to set stream prefix')

    @property
    def wrap_mode(self) -> Literal['bipolar', 'unipolar']:
        return self._wrap_mode

    @wrap_mode.setter
    def wrap_mode(self, mode: Literal['bipolar', 'unipolar']):
        if mode not in ['bipolar', 'unipolar']:
            raise ValueError('Invalid wrap mode. Must be either "bipolar" or "unipolar".')
        self._serial.write_struct('<cB', b'M', 0 if mode == 'bipolar' else 1)
        if self._serial.verify(b''):
            log.debug('Setting wrap mode to %s', mode)
        else:
            raise RuntimeError(f'Failed to set wrap mode to {mode}')

    @property
    def event_transmission(self) -> bool:
        return self._event_transmission

    @event_transmission.setter
    def event_transmission(self, value: bool):
        self._serial.write_struct('<c?', b'V', bool(value))
        if self._serial.verify(b''):
            log.debug('%sabling event transmission', 'En' if value else 'Dis')
        else:
            raise RuntimeError(f'Failed to {"en" if value else "dis"}able event transmission')

    def enable_thresholds(self, enabled_thresholds):
        pass

    def enable_evt_transmission(self):
        pass
