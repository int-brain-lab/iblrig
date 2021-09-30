#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: tests/test_pybpod_config.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Friday, July 9th 2021, 1:13:04 pm
import shutil
import unittest
from pathlib import Path

import iblrig.path_helper as ph
import iblrig.pybpod_config as config
from one.api import ONE


one = ONE(
    base_url="https://test.alyx.internationalbrainlab.org",
    username="test_user",
    password="TapetesBloc18",
)


class TestsPybpodConfig(unittest.TestCase):
    def setUp(self):
        self.project_name = "ibl_mainenlab"
        self.project_name_nok = "bla"
        self.project_path = Path(ph.get_iblrig_params_folder()) / self.project_name

    def test_create_alyx(self):
        p = config.create_local_project_from_alyx(self.project_name, one=one, force=False)
        self.assertTrue(self.project_path.exists())
        self.assertTrue(isinstance(p, dict))

        u = config.create_ONE_alyx_user(self.project_name, one=one, force=False)
        self.assertTrue(self.project_path.joinpath("users", one.alyx.user).exists())
        self.assertTrue(self.project_path.joinpath("users", "_iblrig_test_user").exists())
        self.assertTrue(self.project_path.exists())
        self.assertTrue(isinstance(u, dict))

        s = config.create_local_subjects_from_alyx_project(self.project_name, one=one, force=False)
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
