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
        test_subject_name = '_iblrig_test_mouse'
        self.local_dir = tempfile.TemporaryDirectory()
        self.remote_dir = tempfile.TemporaryDirectory()

        def create_local_session():
            local_session_folder = \
                Path(self.local_dir.name) / 'Subjects' / test_subject_name / '1900-01-01' / '001'
            local_session_folder.mkdir(parents=True)
            return str(local_session_folder)

        def create_remote_subject():
            remote_subject_dir = Path(self.remote_dir.name) / 'Subjects'
            remote_subject_dir.mkdir(parents=True)
            return str(remote_subject_dir)

        def assert_values(previous_session_folders):
            self.assertTrue(isinstance(previous_session_folders, list))
            if previous_session_folders:
                # returned list is not empty and should contain strings
                for session_folder in previous_session_folders:
                    self.assertTrue(isinstance(session_folder, str))

        # Test for an existing subject, local does exist and remote does exist
        # Create local session and remote subject temp directories
        test_local_session_folder = create_local_session()
        test_remote_subject_folder = create_remote_subject()

        # Call the function
        test_previous_session_folders = ph.get_previous_session_folders(
            test_subject_name, test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder)
        assert_values(test_previous_session_folders)

        # Test for an existing subject, local does exist and remote does NOT exist
        self.remote_dir.cleanup()
        # Call the function
        test_previous_session_folders = ph.get_previous_session_folders(
            test_subject_name, test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder)
        assert_values(test_previous_session_folders)

        # Test for an existing subject, local does NOT exist and remote does exist
        self.local_dir.cleanup()
        test_remote_subject_folder = create_remote_subject()
        # Call the function
        test_previous_session_folders = ph.get_previous_session_folders(
            test_subject_name, test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder)
        assert_values(test_previous_session_folders)

        # Test for an existing subject, local does NOT exist and remote does NOT exist
        self.local_dir.cleanup()
        self.remote_dir.cleanup()
        # Call the function
        test_previous_session_folders = ph.get_previous_session_folders(
            test_subject_name, test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder)
        assert_values(test_previous_session_folders)

        # Test for a new subject
        test_new_subject_name = '_new_iblrig_test_mouse'
        test_new_session_folder = \
            Path(self.local_dir.name) / 'Subjects' / test_new_subject_name / '1900-01-01' / '001'
        test_previous_session_folders = ph.get_previous_session_folders(
            test_new_subject_name, str(test_new_session_folder))
        self.assertTrue(isinstance(test_previous_session_folders, list))
        self.assertTrue(not test_previous_session_folders) # returned list should be empty

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
