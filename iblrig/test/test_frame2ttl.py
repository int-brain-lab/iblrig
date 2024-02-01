import unittest
from unittest.mock import Mock, patch

from iblrig.frame2ttl import Frame2TTL


class TestFrame2TTL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_port_info = Mock()
        cls.mock_port_info.vid = 0x16C0
        cls.mock_port_info.pid = 0x0483
        cls.mock_port_info.device = 'FakePort'

    @patch('iblrig.frame2ttl.comports')
    @patch('iblrig.frame2ttl.SerialSingleton.__init__')
    def test_wrong_device(self, mock_super_init, mock_comports):
        self.mock_port_info.vid = 0x0000
        mock_comports.return_value = (self.mock_port_info,)
        with self.assertRaises(OSError) as e:
            Frame2TTL(port='FakePort')
        mock_super_init.assert_not_called()

    @patch('iblrig.frame2ttl.comports')
    @patch('iblrig.frame2ttl.SerialSingleton.__init__')
    def test_samd21_in_bootload_mode(self, mock_super_init, mock_comports):
        self.mock_port_info.vid = 0x1B4F
        self.mock_port_info.pid = 0x0D21
        mock_comports.return_value = (self.mock_port_info,)
        with self.assertRaises(OSError) as e:
            Frame2TTL(port='FakePort')
        mock_super_init.assert_not_called()

    # TODO: add coverage
    # @patch('iblrig.frame2ttl.comports')
    # @patch('iblrig.frame2ttl.SerialSingleton', autospec=True)
    # def test_samd21_magic_baud_rate(self, mock_serial_singleton, mock_comports):
    #     self.mock_port_info.vid = 0x1B4F
    #     self.mock_port_info.pid = 0x8D21
    #     mock_comports.return_value = (self.mock_port_info,)
    #     with self.assertRaises(OSError) as e:
    #         Frame2TTL(port='FakePort')
    #     serial_singleton_instance = mock_serial_singleton.return_value
    #     print(dir(serial_singleton_instance))
    #     print(dir(serial_singleton_instance.__init__))
    #     serial_singleton_instance.__init__.assert_called_once()
