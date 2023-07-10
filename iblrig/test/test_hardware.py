import unittest
import sys

from iblrig.hardware import Bpod


class TestHardware(unittest.TestCase):

    def test_singleton(self):

        bpods = {Bpod() for i in range(1000)}
        assert (len(bpods) == 1)