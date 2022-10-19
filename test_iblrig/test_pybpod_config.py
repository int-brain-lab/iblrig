import shutil
import unittest
from pathlib import Path

import iblrig.ibllib_calls as libcalls
import iblrig.params as params
import iblrig.pybpod_config as config
from iblrig import path_helper


class TestsPybpodConfig(unittest.TestCase):
    def setUp(self):
        self.project_name = "ibl_mainenlab"
        self.project_name_nok = "bla"
        params.write_params_file(force=True)
        pars = params.load_params_file()
        pars["NAME"] = "_iblrig_mainenlab_ephys_0"
        params.write_params_file(pars, force=True)
        self.project_path = Path(path_helper.get_iblrig_params_folder()) / self.project_name
        libcalls.call_one_get_project_data(self.project_name, one_test=True)

    def test_create_alyx(self):
        p = config.create_local_project_from_alyx(self.project_name, force=False)
        self.assertTrue(self.project_path.exists())
        self.assertTrue(isinstance(p, dict))

        u = config.create_ONE_alyx_user(self.project_name, force=False)
        self.assertTrue(self.project_path.joinpath("users", "test_user").exists())
        self.assertTrue(self.project_path.joinpath("users", "_iblrig_test_user").exists())
        self.assertTrue(self.project_path.exists())
        self.assertTrue(isinstance(u, dict))

        s = config.create_local_subjects_from_alyx_project(self.project_name, force=False)
        self.assertTrue(self.project_path.joinpath("subjects", "clns0730").exists())
        self.assertTrue(self.project_path.joinpath("subjects", "flowers").exists())
        self.assertTrue(self.project_path.joinpath("subjects", "IBL_46").exists())
        self.assertTrue(self.project_path.joinpath("subjects", "_iblrig_calibration").exists())
        self.assertTrue(self.project_path.joinpath("subjects", "_iblrig_test_mouse").exists())
        self.assertTrue(isinstance(s, list))

    def tearDown(self):
        shutil.rmtree(self.project_path)


if __name__ == "__main__":
    unittest.main(exit=False)
