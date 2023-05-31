import unittest
from pathlib import Path

from iblrig import path_helper


class TestPathHelper(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_iblrig_path(self):
        p = path_helper.get_iblrig_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_iblrig_params_path(self):
        p = path_helper.get_iblrig_params_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_commit_hash(self):
        import subprocess

        out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        # Run it
        ch = path_helper.get_commit_hash(str(path_helper.get_iblrig_path()))
        self.assertTrue(out == ch)

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
