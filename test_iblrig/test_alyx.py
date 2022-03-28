import unittest

from pathlib import Path
import iblrig.ibllib_calls as calls


class TestIbllibCalls(unittest.TestCase):
    def setUp(self):
        pass

    def test_call_one_get_project_data(self):
        calls.call_one_get_project_data("ibl_mainenlab", one_test=True)
        self.assertTrue(Path().home().joinpath("TempAlyxProjectData").exists())
        self.assertTrue(Path().home().joinpath("TempAlyxProjectData", "ibl_mainenlab_subjects.json").exists())

    def test_call_one_sync_params(self):
        resp = calls.call_one_sync_params(one_test=True)
        self.assertTrue(not resp.stderr.decode())

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
