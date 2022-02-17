import tempfile
import unittest
from pathlib import Path

import iblrig.path_helper as ph


class TestPathHelper(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_network_drives(self):
        nd = ph.get_network_drives()
        print(nd)
        # outs = ["C:\\", "Y:\\", "~/Projects/IBL/github/iblserver"]
        # self.assertTrue(all([x in outs for x in nd]))

    def test_get_iblserver_data_folder(self):
        outs = [
            "Y:\\",
            "Y:\\Subjects",
            None,
            "~/Projects/IBL/github/iblserver",
            "~/Projects/IBL/github/iblserver/Subjects",
        ]
        df = ph.get_iblserver_data_folder(subjects=True)
        self.assertTrue(df in outs)
        df = ph.get_iblserver_data_folder(subjects=False)
        self.assertTrue(df in outs)

    def test_get_iblrig_folder(self):
        f = ph.get_iblrig_folder()
        self.assertTrue(isinstance(f, str))
        self.assertTrue("iblrig" in f)

    def test_get_iblrig_params_folder(self):
        f = ph.get_iblrig_params_folder()
        self.assertTrue(isinstance(f, str))
        self.assertTrue("iblrig_params" in f)
        fp = Path(f)
        self.assertTrue(str(fp.parent) == str(Path(ph.get_iblrig_folder()).parent))

    def test_get_iblrig_data_folder(self):
        df = ph.get_iblrig_data_folder(subjects=False)
        self.assertTrue(isinstance(df, str))
        self.assertTrue("iblrig_data" in df)
        self.assertTrue("Subjects" not in df)
        dfs = ph.get_iblrig_data_folder(subjects=True)
        self.assertTrue(isinstance(dfs, str))
        self.assertTrue("iblrig_data" in dfs)
        self.assertTrue("Subjects" in dfs)

    def test_get_commit_hash(self):
        import subprocess

        out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        # Run it
        ch = ph.get_commit_hash(ph.get_iblrig_folder())
        self.assertTrue(out == ch)

    def test_get_previous_session_folders(self):
        # Create temp directories for an existing subject test
        self.dir = tempfile.TemporaryDirectory()
        test_subject_name = '_iblrig_test_mouse'
        test_session_folder = \
            Path(self.dir.name) / 'Subjects' / test_subject_name / '2022-02-11' / '001'
        test_session_folder.mkdir(parents=True)

        # Test for an existing subject
        test_previous_session_folders = ph.get_previous_session_folders(
            test_subject_name, str(test_session_folder))
        self.assertTrue(isinstance(test_previous_session_folders, list))
        if test_previous_session_folders:  # returned list is not empty and should contain strings
            for test_a_previous_session_folder in test_previous_session_folders:
                self.assertTrue(isinstance(test_a_previous_session_folder, str))

        # Test for a new subject
        test_new_subject_name = '_new_iblrig_test_mouse'
        test_new_session_folder = \
            Path(self.dir.name) / 'Subjects' / test_new_subject_name / '2022-02-11' / '001'
        test_previous_session_folders = ph.get_previous_session_folders(
            test_new_subject_name, str(test_new_session_folder))
        self.assertTrue(isinstance(test_previous_session_folders, list))
        self.assertTrue(not test_previous_session_folders)

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
