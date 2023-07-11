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
        self.assertEqual(Bpod._instances.keys(), {'', 'COM3', 'COM4'})
        bpod_None.__del__()
        self.assertEqual(Bpod._instances.keys(), {'COM3', 'COM4'})
        bpod0.__del__()
        self.assertEqual(Bpod._instances.keys(), {'COM4'})
