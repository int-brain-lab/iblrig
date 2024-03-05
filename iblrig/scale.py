import logging
import re

from serial_singleton import SerialSingleton

log = logging.getLogger(__name__)


class Scale(SerialSingleton):
    # http://dmx.ohaus.com/WorkArea/downloadasset.aspx?id=3600
    # https://dmx.ohaus.com/WorkArea/showcontent.aspx?id=4294974227

    def __init__(self, *args, **kwargs):
        super().__init__(*args, baudrate=9600, timeout=5, **kwargs)
        self.assert_setting('ON')
        while self.query_line('1M') == b'ES':
            pass
        self.assert_setting('1M')  # set current application mode to WEIGH
        self.assert_setting('1U')  # set unit to grams
        self.assert_setting('0FMT')  # use New Scout print format
        self.handshake()

    def assert_setting(self, query: str, expected_response: str = b'OK!') -> None:
        assert self.query_line(query) == expected_response

    def query_line(self, query: str) -> str:
        self.reset_input_buffer()
        self.write(query + '\r\n')
        return self.readline().rstrip(b'\r\n')

    def handshake(self) -> bool:
        v = self.query_line('V')
        sn = self.query_line('PSN')
        log.debug(f'Connected to OHAUS scale on {self.portstr}, {v}, {sn}')

    def zero(self) -> None:
        self.assert_setting('Z')

    def tare(self) -> None:
        self.assert_setting('T')

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

    def get_grams(self) -> tuple[float, bool]:
        """
        Obtain weight reading and stability indicator

        Returns
        -------
        float
            Weight reading in grams
        bool
            Stability indicator: True if scale is stable, False if not
        """
        data = self.query_line('IP')
        match = re.match(rb'\s*([-\d\.]+)\s*(\w)\s(.)', data)
        if match is None:
            grams = float('nan')
            stable = False
        elif match.groups()[1] != b'g':
            self.assert_setting('1U')
            return self.get_grams()
        else:
            grams = float(match.groups()[0])
            stable = match.groups()[2] == b' '
        return grams, stable
