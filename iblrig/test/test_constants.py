import unittest

from iblrig import constants


class TestConstants(unittest.TestCase):
    def test_bonsai_folder_exists(self):
        assert constants.BONSAI_EXE.parent.exists()
