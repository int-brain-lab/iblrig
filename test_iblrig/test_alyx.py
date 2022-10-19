import shutil
import unittest
from pathlib import Path

import iblrig.ibllib_calls as calls
import iblrig.params as params
from iblrig import path_helper


class TestIbllibCalls(unittest.TestCase):
    def setUp(self):
        self.project_name = "ibl_mainenlab"
        self.one_test = True
        params.write_params_file(force=True)
        pars = params.load_params_file()
        pars["NAME"] = "_iblrig_mainenlab_ephys_0"
        params.write_params_file(pars, force=True)

    def test_call_one_sync_params(self):
        calls.call_one_sync_params(one_test=self.one_test)

    def test_call_one_get_project_data(self):
        calls.call_one_get_project_data(self.project_name, one_test=self.one_test)
        alyx_temp_path = Path(path_helper.get_iblrig_temp_alyx_proj_folder())
        self.assertTrue(alyx_temp_path.exists())
        alyx_temp_subjects_path = alyx_temp_path / Path(f"{self.project_name}_subjects.json")
        self.assertTrue(alyx_temp_subjects_path.exists())

    def tearDown(self):
        shutil.rmtree(calls.ROOT_FOLDER, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(exit=False)
