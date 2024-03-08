import logging
import re
from dataclasses import dataclass

from iblrig.serial_singleton import SerialSingleton

log = logging.getLogger(__name__)


@dataclass
class ScaleData:
    weight: float = float('nan')
    unit: str = 'g'
    stable: bool = False
    mode: str = ''


class Scale(SerialSingleton):
    # http://dmx.ohaus.com/WorkArea/downloadasset.aspx?id=3600
    # https://dmx.ohaus.com/WorkArea/showcontent.aspx?id=4294974227
    _re_pattern = re.compile(rb'\s*(\S+)\s+(\w+)\s(.)\s{1,3}(\w{0,2})')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, baudrate=9600, timeout=5, **kwargs)
        self.assert_setting('ON')
        while self.query_line('1M') == b'ES':
            pass
        self.assert_setting('1M')  # set current application mode to WEIGH
        self.assert_setting('1U')  # set unit to grams
        self.assert_setting('0FMT')  # use New Scout print format
        log.debug(f'Connected to OHAUS scale on {self.portstr}')

    def assert_setting(self, query: str, expected_response: str = b'OK!', do_raise: bool = True) -> bool:
        success = self.query_line(query) == expected_response
        if do_raise and not success:
            raise AssertionError
        return success

    def query_line(self, query: str) -> bytes:
        self.reset_input_buffer()
        self.write(query + '\r\n')
        return self.readline().rstrip(b'\r\n')

    def zero(self) -> bool:
        success = self.assert_setting('Z', do_raise=False)
        if success:
            self.get_stable_grams()
        return success

    def tare(self) -> bool:
        weight, _, _, mode = self._split_query()
        if weight == b'0.00' and mode != b'N':
            return True
        success = self.assert_setting('T', do_raise=False)
        if success:
            self.get_stable_grams()
        return success

    @property
    def grams(self) -> float:
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
        data = self.query_line(query)
        if (match := re.fullmatch(self._re_pattern, data)) is None:
            return b'nan', b'g', b'?', b''
        else:
            return match.groups()

    def get_grams(self) -> tuple[float, bool]:
        """
        Obtain weight reading in grams and stability indicator

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
