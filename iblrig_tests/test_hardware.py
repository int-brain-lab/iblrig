import unittest

from iblrig.hardware import Bpod


class TestBpod(unittest.TestCase):
    def test_singleton(self):
        bpod_none = Bpod()
        bpod0 = Bpod('COM3', connect=False)
        bpod1 = Bpod(serial_port='COM3', connect=False)
        bpod2 = Bpod(serial_port='COM4', connect=False)
        assert bpod0 is bpod1
        assert bpod0 is not bpod2
        assert bpod_none is not bpod1
        self.assertEqual({'', 'COM3', 'COM4'}, Bpod._instances.keys())
        bpod_none.__del__()
        self.assertEqual({'COM3', 'COM4'}, Bpod._instances.keys())
        bpod0.__del__()
        self.assertEqual({'COM4'}, Bpod._instances.keys())

    def test_soft_codes(self):
        bpod = Bpod('COM3', connect=False)
        softcode_dict = {5: lambda: 7, 6: lambda: 8}
        bpod.register_softcodes(softcode_dict)
        self.assertEqual(7, bpod.softcode_handler_function(5))
        self.assertEqual(8, bpod.softcode_handler_function(6))
        with self.assertRaises(KeyError):
            bpod.softcode_handler_function(1)
