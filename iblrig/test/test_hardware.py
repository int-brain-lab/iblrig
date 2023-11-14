import unittest

from iblrig.hardware import Bpod


class TestHardware(unittest.TestCase):
    def test_singleton(self):
        bpod_None = Bpod()
        bpod0 = Bpod('COM3', connect=False)
        bpod1 = Bpod(serial_port='COM3', connect=False)
        bpod2 = Bpod(serial_port='COM4', connect=False)
        assert bpod0 is bpod1
        assert bpod0 is not bpod2
        assert bpod_None is not bpod1
        self.assertEqual({'', 'COM3', 'COM4'}, Bpod._instances.keys())
        bpod_None.__del__()
        self.assertEqual({'COM3', 'COM4'}, Bpod._instances.keys())
        bpod0.__del__()
        self.assertEqual({'COM4'}, Bpod._instances.keys())
