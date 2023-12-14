import unittest

from iblrig import constants


class TestConstants(unittest.TestCase):
    def test_folders_exist(self):
        assert constants.BONSAI_EXE.parent.exists()
        assert constants.SETTINGS_PATH.exists()
