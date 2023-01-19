import unittest
from iblrig.hardware import Bpod


class TestBpod(unittest.TestCase):

    def test_bpod(self):
        bpod = Bpod()
        self.assertIsNotNone(bpod.hardware)
