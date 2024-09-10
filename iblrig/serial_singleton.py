import ctypes
import logging
import re
import struct
import threading
from collections.abc import Generator
from typing import Any, overload

import numpy as np
import serial
from serial.serialutil import to_bytes  # type: ignore[attr-defined]
from serial.tools import list_ports

log = logging.getLogger(__name__)


class SerialSingletonException(serial.SerialException):
    pass


class SerialSingleton(serial.Serial):
    _instances: dict[str | None, serial.Serial] = dict()
    _initialized = False
    _lock = threading.RLock()

    def __new__(cls, port: str | None = None, serial_number: str | None = None, *args, **kwargs):
        # identify the device by its serial number
        if port is None:
            if serial_number is not None:
                port = get_port_from_serial_number(serial_number)
                if port is None:
                    raise SerialSingletonException(f'No device matching serial number `{serial_number}`')
            else:
                raise ValueError('Neither port nor serial number provided')

        # implement singleton
        with cls._lock:
            instance = SerialSingleton._instances.get(port, None)
            if instance is None:
                log.debug(f'Creating new {cls.__name__} instance on {port}')
                instance = super().__new__(cls)
                SerialSingleton._instances[port] = instance
            else:
                instance_name = type(instance).__name__
                if instance_name != cls.__name__:
                    raise SerialSingletonException(f'{port} is already in use by an instance of {instance_name}')
                log.debug(f'Using existing {instance_name} instance on {port}')
            return instance

    def __init__(self, port: str | None = None, connect: bool = True, **kwargs) -> None:
        if not self._initialized:
            super().__init__(**kwargs)
            serial.Serial.port.fset(self, port)  # type: ignore[attr-defined]
            self.port_info = next((p for p in list_ports.comports() if p.device == self.port), None)
            self._initialized = True
        if not getattr(self, 'is_open', False) and connect is True:
            self.open()

    def __del__(self) -> None:
        self.close()
        with self._lock:
            if hasattr(self, 'port') and self.port in SerialSingleton._instances:
                log.debug(f'Deleting {type(self).__name__} instance on {self.port}')
                SerialSingleton._instances.pop(self.port)

    def open(self) -> None:
        if self.port is not None:
            super().open()
            log.debug(f'Serial connection to {self.port} opened')

    def close(self) -> None:
        if getattr(self, 'is_open', False):
            super().close()
            log.debug(f'Serial connection to {self.port} closed')

    @property
    def port(self) -> str | None:
        """
        Get the serial device's communication port.

        Returns
        -------
        str
            The serial port (e.g., 'COM3', '/dev/ttyUSB0') used by the serial device.
        """
        return super().port

    @port.setter
    def port(self, port: str | None):
        """
        Set the serial device's communication port.

        This setter allows changing the communication port before the object is
        instantiated. Once the object is instantiated, attempting to change the port
        will raise a SerialSingletonException.

        Parameters
        ----------
        port : str
            The new communication port to be set (e.g., 'COM3', '/dev/ttyUSB0').

        Raises
        ------
        SerialSingletonException
            If an attempt is made to change the port after the object has been
            instantiated.
        """
        if self._initialized:
            raise SerialSingletonException('Port cannot be changed after instantiation.')
        if port is not None:
            serial.Serial.port.fset(self, port)  # type: ignore[attr-defined]

    def write(self, data) -> int | None:
        return super().write(self.to_bytes(data))

    def write_packed(self, format_string: str, *data: Any) -> int | None:
        """
        Pack values according to format string and write to serial device.

        Parameters
        ----------
        format_string : str
            Format string describing the data layout for packing the data
            following the conventions of the :mod:`struct` module.
            See https://docs.python.org/3/library/struct.html#format-characters

        data : Any
            Data to be written to the serial device.

        Returns
        -------
        int or None
            Number of bytes written to the serial device.
        """
        size = struct.calcsize(format_string)
        buffer = ctypes.create_string_buffer(size)
        struct.pack_into(format_string, buffer, 0, *data)
        return super().write(buffer)

    @overload
    def read(self, data_specifier: int = 1) -> bytes: ...

    @overload
    def read(self, data_specifier: str) -> tuple[Any, ...]: ...

    def read(self, data_specifier=1):
        r"""
        Read data from the serial device.

        Parameters
        ----------
        data_specifier : int or str, default: 1
            The number of bytes to receive from the serial device, or a format string
            for unpacking.

            When providing an integer, the specified number of bytes will be returned
            as a bytestring. When providing a `format string`, the data will be
            unpacked into a tuple accordingly. Format strings follow the conventions of
            the :mod:`struct` module.

            .. _format string:
                https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        bytes or tuple[Any]
            Data returned by the serial device. By default, data is formatted as a
            bytestring. Alternatively, when provided with a format string, data will
            be unpacked into a tuple according to the specified format string.
        """
        if isinstance(data_specifier, str):
            n_bytes = struct.calcsize(data_specifier)
            return struct.unpack(data_specifier, super().read(n_bytes))
        else:
            return super().read(data_specifier)

    @overload
    def query(self, query: Any, data_specifier: int = 1) -> bytes: ...

    @overload
    def query(self, query: Any, data_specifier: str) -> tuple[Any, ...]: ...

    def query(self, query, data_specifier=1):
        r"""
        Query data from the serial device.

        This method is a combination of :py:meth:`write` and :py:meth:`read`.

        Parameters
        ----------
        query : Any
            Query to be sent to the serial device.
        data_specifier : int or str, default: 1
            The number of bytes to receive from the serial device, or a format string
            for unpacking.

            When providing an integer, the specified number of bytes will be returned
            as a bytestring. When providing a `format string`_, the data will be
            unpacked into a tuple accordingly. Format strings follow the conventions of
            the :py:mod:`struct` module.

            .. _format string:
                https://docs.python.org/3/library/struct.html#format-characters

        Returns
        -------
        bytes or tuple[Any]
            Data returned by the serial device. By default, data is formatted as a
            bytestring. Alternatively, when provided with a format string, data will be
            unpacked into a tuple according to the specified format string.
        """
        self.write(query)
        return self.read(data_specifier)

    @staticmethod
    def to_bytes(data: Any) -> bytes:
        """
        Convert data to bytestring.

        This method extends :meth:`serial.to_bytes` with support for NumPy types,
        strings (interpreted as utf-8) and lists.

        Parameters
        ----------
        data : Any
            Data to be converted to bytestring.

        Returns
        -------
        bytes
            Data converted to bytestring.
        """
        match data:
            case np.ndarray() | np.generic():
                return data.tobytes()
            case int():
                return data.to_bytes(1, 'little')
            case str():
                return data.encode('utf-8')
            case list():
                return b''.join([SerialSingleton.to_bytes(item) for item in data])
            case _:
                return to_bytes(data)  # type: ignore[no-any-return]


def filter_ports(**kwargs: dict[str, Any]) -> Generator[str, None, None]:
    """
    Filter serial ports based on specified criteria.

    Parameters
    ----------
    **kwargs : keyword arguments
        Filtering criteria for serial ports. Each keyword should correspond
        to an attribute of the serial port object (ListPortInfo). The values associated
        with the keywords are used to filter the ports based on various conditions.

    Yields
    ------
    str
        The device name of a filtered serial port that meets all specified criteria.

    Examples
    --------
    To filter ports by manufacturer and product:

    >>> for port in filter_ports(manufacturer="Arduino", product="Uno"):
    ...     print(port)

    Raises
    ------
    ValueError
        If a specified attribute does not exist for a port.

    Notes
    -----
    - The function uses regular expressions for string matching when both actual
      and expected values are strings.
    """
    for port in list_ports.comports():
        yield_port = True
        for key, expected_value in kwargs.items():
            if not hasattr(port, key):
                raise ValueError(f"Attribute '{key}' not found for port {port}")
            actual_value = getattr(port, key)
            if isinstance(actual_value, str) and isinstance(expected_value, str):
                if bool(re.search(expected_value, actual_value)):
                    continue
            elif actual_value == expected_value:
                continue
            yield_port = False
            break
        if yield_port:
            yield port.device


def get_port_from_serial_number(serial_number: str) -> str | None:
    """
    Retrieve the com port of a USB serial device identified by its serial number.

    Parameters
    ----------
    serial_number : str
       The serial number of the USB device that you want to obtain the communication
       port of.

    Returns
    -------
    str or None
       The communication port of the USB serial device that matches the serial number
       provided by the user. The function will return None if no such device was found.
    """
    port_info = list_ports.comports()
    port_match = next((p for p in port_info if p.serial_number == serial_number), None)
    return port_match.name if port_match else None


def get_serial_number_from_port(port: str | None) -> str | None:
    """
    Retrieve the serial number of a USB serial device identified by its com port.

    Parameters
    ----------
    port : str
        The communication port of the USB serial device for which you want to retrieve
        the serial number.

    Returns
    -------
    str or None
        The serial number of the USB serial device corresponding to the provided
        communication port. Returns None if no device matches the port.
    """
    port_info = list_ports.comports()
    port_match = next((p for p in port_info if p.name == port), None)
    return port_match.serial_number if port_match else None
