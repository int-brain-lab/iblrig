import logging
import struct
from typing import Literal, overload

import numpy as np
from bpod_core.com import ExtendedSerial
from numpy.typing import NDArray
from serial import SerialException

log = logging.getLogger(__name__)


class RotaryEncoderModule:
    _name: str = 'Rotary Encoder Module'
    _is_logging: bool = False
    _wrap_point: float = 180.0
    _wrap_mode: Literal['bipolar', 'unipolar'] = 'bipolar'
    _thresholds: list[float] = []
    _max_thresholds: int = 8

    def __init__(self, port: str):
        # handshake / identify hardware version
        self._hardware_version = self.probe(port)

        # set half-point according to the hardware version
        self._half_point = 512 if self._hardware_version == 1 else 2048
        self._factor_tick_to_deg = 180.0 / self._half_point
        self._factor_deg_to_tick = self._half_point / 180.0

        # initialize serial object and set port
        # implemented that awkwardly to get logging from self.open()
        self._serial = ExtendedSerial()
        self._serial.port = port
        self.open()

        # reset to default settings
        self.reset()

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        self.close()

    def _degrees_to_ticks(self, degrees: float) -> int:
        """Convert degrees to ticks."""
        return round(degrees * self._factor_deg_to_tick)

    def _ticks_to_degrees(self, ticks: int) -> float:
        """Convert ticks to degrees."""
        return ticks * self._factor_tick_to_deg

    def _reset_data_streams(self):
        self._serial.write(b'X')
        self._is_logging = False
        log.debug('All data streams reset')

    def reset(self):
        """Reset Rotary Encoder Module to default settings."""
        self.wrap_point = 180.0
        self.thresholds = [-40.0, 40.0]
        # obj.wrapMode = 'bipolar';
        # obj.sendThresholdEvents = 'off';
        # obj.moduleOutputStream = 'off';
        if self._hardware_version == 1:
            self.set_stream_prefix('M')

    @property
    def hardware_version(self) -> int:
        """Hardware version of the connected Rotary Encoder Module."""
        return self._hardware_version

    @property
    def port(self) -> str | None:
        """Port name of the connected Rotary Encoder Module."""
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
    def _ticks(self) -> int:
        return self._serial.query_struct(b'Q', '<i')[0]

    @_ticks.setter
    def _ticks(self, value: int) -> None:
        self._serial.write_struct('<ci', b'P', value)

    @property
    def wrap_point(self) -> float:
        """Get or set the wrap point in degrees."""
        return self._wrap_point

    @wrap_point.setter
    def wrap_point(self, degrees: float) -> None:
        ticks = self._degrees_to_ticks(abs(degrees))
        query = struct.pack('<cI', b'W', ticks)
        if self._serial.verify(query):
            self._wrap_point = self._ticks_to_degrees(ticks)
            log.debug('Setting wrap point to %0.1f degrees', self._wrap_point)
        else:
            raise RuntimeError('Failed to set wrap point')

    @property
    def thresholds(self) -> list[float]:
        """List of thresholds in degrees."""
        return self._thresholds

    @thresholds.setter
    def thresholds(self, degrees: list[float]) -> None:
        if any(abs(threshold) > self._wrap_point for threshold in degrees):
            raise ValueError(f'Threshold values cannot exceed the current wrap point of {self._wrap_point} degrees.')
        if (n_thresholds := len(degrees)) > 8:
            raise ValueError(f'A maximum of {self._max_thresholds} thresholds can be set.')
        ticks = [self._degrees_to_ticks(thresh) for thresh in degrees]
        degrees = [self._ticks_to_degrees(tick) for tick in ticks]
        query = struct.pack(f'<cB{n_thresholds}h', b'T', n_thresholds, *ticks)
        if self._serial.verify(query):
            self._thresholds = degrees
            log.debug('Setting thresholds to [%s] degrees', ', '.join([f'{x:0.1f}' for x in degrees]))
        else:
            raise RuntimeError('Failed to set thresholds')

    @property
    def sd_logging(self) -> bool:
        """The state of SD card logging."""
        return self._is_logging

    @sd_logging.setter
    def sd_logging(self, enable_logging: bool) -> None:
        if enable_logging == self._is_logging:
            return
        if self.hardware_version != 1:
            raise RuntimeError(f'SD card logging is not supported on {self._name} v{self.hardware_version}')
        if enable_logging:
            self._serial.write(b'L')
            log.debug('Logging enabled')
        else:
            self._serial.write(b'F')
            log.debug('Logging disabled')
        self._is_logging = bool(enable_logging)

    @property
    def current_position(self) -> float:
        """Current encoder position in degrees."""
        return self._ticks_to_degrees(self._ticks)

    @current_position.setter
    def current_position(self, degrees: float):
        self._ticks = self._degrees_to_ticks(degrees)

    def set_zero_position(self) -> None:
        """Reset current encoder position to zero."""
        self._serial.write(b'Z')

    def enable_logging(self):
        """
        Enables logging to the SD Card.

        Only supported for hardware version 1.

        Raises
        ------
        RuntimeError
            If the hardware version is not 1.
        """
        self.sd_logging = True

    def disable_logging(self):
        """Disables the logging to the SD Card."""
        self.sd_logging = False

    def get_logged_data(self) -> NDArray[np.void]:
        """Retrieve logged data from the SD card.

        Returns
        -------
        numpy.ndarray
            Structured NumPy array with one element per logged sample.
            Each element has the following fields:

            - ``time`` :class:`numpy.timedelta64` with unit ``us``
            - ``degrees`` :class:`numpy.float32`
        """
        if self.hardware_version != 1:
            raise RuntimeError(f'SD card logging is not supported on {self._name} v{self.hardware_version}')

        self.sd_logging = False  # stop logging before retrieving data

        n_values = self._serial.query_struct(b'R', '<I')[0]
        buffer = self._serial.read(n_values * 8)

        dtype = np.dtype([('time', np.uint32), ('ticks', np.int32)])
        raw = np.frombuffer(buffer, dtype=dtype)

        out_dtype = np.dtype([('time', 'timedelta64[us]'), ('degrees', 'f4')])
        out = np.empty(raw.shape[0], dtype=out_dtype)
        out['time'] = raw['time'].astype('timedelta64[us]')
        out['degrees'] = raw['ticks'] * self._factor_tick_to_deg

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

    def enable_thresholds(self, enabled_thresholds):
        pass

    def enable_evt_transmission(self):
        pass
