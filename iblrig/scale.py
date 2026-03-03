"""Serial interface for OHAUS Scout scales."""

import logging
import re
from dataclasses import dataclass

from iblrig.serial_singleton import SerialSingleton

log = logging.getLogger(__name__)

# http://dmx.ohaus.com/WorkArea/downloadasset.aspx?id=3600
# https://dmx.ohaus.com/WorkArea/showcontent.aspx?id=4294974227
RE_PATTERN = re.compile(rb'\s*(\S+)\s+(\w+)\s(.)\s{1,3}(\w{0,2})')


@dataclass
class ScaleData:
    """Structured weight measurement returned by the scale.

    Attributes
    ----------
    weight : float
        Weight reading (NaN if unavailable).
    unit : str
        Unit of measurement (default ``'g'`` for grams).
    stable : bool
        True if the scale reading is stable.
    mode : str
        Current scale operating mode string.
    """

    weight: float = float('nan')
    unit: str = 'g'
    stable: bool = False
    mode: str = ''


class Scale(SerialSingleton):
    """Serial interface to an OHAUS Scout scale.

    Communicates via RS-232 using the OHAUS New Scout print-format command set.
    Inherits from :class:`SerialSingleton` to prevent duplicate serial connections.
    On construction the scale is configured for WEIGH mode, gram units, and New
    Scout print format.

    Parameters
    ----------
    *args
        Positional arguments forwarded to :class:`SerialSingleton`.
    **kwargs
        Keyword arguments forwarded to :class:`SerialSingleton` (e.g. ``port``).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, baudrate=9600, timeout=5, **kwargs)
        self.assert_setting('ON')
        while self.query_line('1M') == b'ES':
            pass
        self.assert_setting('1M')  # set current application mode to WEIGH
        self.assert_setting('1U')  # set unit to grams
        self.assert_setting('0FMT')  # use New Scout print format
        log.debug(f'Connected to OHAUS scale on {self.portstr}')

    def assert_setting(self, query: str, expected_response: bytes = b'OK!', do_raise: bool = True) -> bool:
        """Send a command and verify the scale's response.

        Parameters
        ----------
        query : str
            Command string to send to the scale.
        expected_response : bytes, optional
            Expected response bytes. Default is ``b'OK!'``.
        do_raise : bool, optional
            If True, raise :exc:`AssertionError` when the response does not
            match *expected_response*. Default is True.

        Returns
        -------
        bool
            True if the response matches *expected_response*, False otherwise.

        Raises
        ------
        AssertionError
            If *do_raise* is True and the response does not match
            *expected_response*.
        """
        success = self.query_line(query) == expected_response
        if do_raise and not success:
            raise AssertionError
        return success

    def query_line(self, query: str) -> bytes:
        """Send a command to the scale and return the response line.

        The input buffer is flushed before writing to avoid stale data.
        CR+LF is appended to *query* automatically and stripped from the
        response.

        Parameters
        ----------
        query : str
            Command string to send to the scale.

        Returns
        -------
        bytes
            Response bytes with trailing CR+LF stripped.
        """
        self.reset_input_buffer()
        self.write(query + '\r\n')
        return self.readline().rstrip(b'\r\n')

    def zero(self) -> bool:
        """Zero the scale and wait for a stable reading.

        Returns
        -------
        bool
            True if zeroing succeeded, False otherwise.
        """
        success = self.assert_setting('Z', do_raise=False)
        if success:
            self.get_stable_grams()
        return success

    def tare(self) -> bool:
        """Tare the scale and wait for a stable reading.

        Skips the tare command if the scale already reads zero in net (tared)
        mode. Blocks until the reading is stable after a successful tare.

        Returns
        -------
        bool
            True if taring succeeded or was already tared, False otherwise.
        """
        weight, _, _, mode = self._split_query()
        if weight == b'0.00' and mode != b'N':
            return True
        success = self.assert_setting('T', do_raise=False)
        if success:
            self.get_stable_grams()
        return success

    @property
    def grams(self) -> float:
        """Current weight reading in grams (instantaneous, may be unstable).

        Returns
        -------
        float
            Weight reading in grams.
        """
        return self.get_grams()[0]

    def get_stable_grams(self) -> float:
        """
        Blocking function that will only return a weight reading once the scale is stable.

        Returns
        -------
        float
            Stable weight reading (grams)
        """
        while not (return_value := self.get_grams())[1]:
            pass
        return return_value[0]

    def _split_query(self, query: str = 'IP') -> tuple[bytes, ...]:
        """Send a query and parse the raw scale response into components.

        Parameters
        ----------
        query : str, optional
            Command to send to the scale. Default is ``'IP'`` (immediate
            print — returns the current weight).

        Returns
        -------
        tuple of bytes
            Four-element tuple ``(weight, unit, stability_flag, mode)``.
            Returns ``(b'nan', b'g', b'?', b'')`` if the response cannot be
            parsed by :data:`RE_PATTERN`.
        """
        data = self.query_line(query)
        if (match := re.fullmatch(RE_PATTERN, data)) is None:
            return b'nan', b'g', b'?', b''
        else:
            return match.groups()

    def get_grams(self) -> tuple[float, bool]:
        """
        Obtain weight reading in grams and stability indicator.

        Returns
        -------
        float
            Weight reading in grams
        bool
            Stability indicator: True if scale is stable, False if not
        """
        weight, unit, stable, _ = self._split_query('IP')
        if unit != b'g':
            self.assert_setting('1U')
            return self.get_grams()
        return float(weight), stable == b' '
