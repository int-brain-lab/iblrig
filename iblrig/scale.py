import re

from serial_singleton import SerialSingleton


class Scale(SerialSingleton):
    # http://dmx.ohaus.com/WorkArea/downloadasset.aspx?id=3600
    # https://dmx.ohaus.com/WorkArea/showcontent.aspx?id=4294974227

    def __init__(self, *args, **kwargs):
        super().__init__(*args, baudrate=9600, timeout=5, **kwargs)
        self.assert_setting('1M')
        self.assert_setting('0FMT')

    def assert_setting(self, query: str, expected_response: str = 'OK!') -> None:
        assert self.query_line(query) == expected_response

    def query_line(self, query: str) -> str:
        self.reset_input_buffer()
        self.write(query + '\r\n')
        return self.readline().strip().decode()

    def zero(self) -> None:
        self.assert_setting('Z')

    @property
    def version(self) -> str:
        return self.query_line('V')

    @property
    def grams(self) -> float:
        return self.get_grams()[0]

    def get_grams(self) -> tuple[float, bool]:
        self.assert_setting('1U')
        data = self.query_line('IP')
        if (match := re.match(r'^(?P<grams>[\d\.]+)\s*g', data)) is not None:
            grams = float(match.group('grams'))
        else:
            grams = float('nan')
        stable = not bool(re.search(r'\?$', data))
        return grams, stable
