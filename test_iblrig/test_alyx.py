import unittest
import subprocess
import shutil

from pathlib import Path
import iblrig.ibllib_calls as calls
import iblrig.params as params


class TestIbllibCalls(unittest.TestCase):
    def setUp(self):
        self.project_name = "ibl_mainenlab"
        self.one_test = True
        pars = params.write_params_file(force=True)
        pars = params.load_params_file()
        pars['NAME'] = '_iblrig_mainenlab_ephys_0'
        params.write_params_file(pars, force=True)

    def test_call_one_sync_params(self):
        resp = calls.call_one_sync_params(one_test=self.one_test)
        self.assertTrue(isinstance(resp, subprocess.CompletedProcess))
        self.assertTrue(resp.returncode == 0)

    def test_call_one_get_project_data(self):
        calls.call_one_get_project_data(self.project_name, one_test=self.one_test)
        self.assertTrue(Path().home().joinpath("TempAlyxProjectData").exists())
        self.assertTrue(Path().home().joinpath("TempAlyxProjectData", f"{self.project_name}_subjects.json").exists())

    def tearDown(self):
        shutil.rmtree(calls.ROOT_FOLDER, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(exit=False)
