import tempfile
import unittest
from pathlib import Path

from iblrig import path_helper


class TestPathHelper(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_remote_server_path(self):
        p = path_helper.get_remote_server_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_iblrig_local_data_path(self):
        # test without specifying subject arg
        p = path_helper.get_iblrig_local_data_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)
        self.assertTrue(p.parts[-1] == "Subjects")

        # test specifying subject=True
        p = path_helper.get_iblrig_local_data_path(subjects=True)
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)
        self.assertTrue(p.parts[-1] == "Subjects")

        # test specifying subject=False
        p = path_helper.get_iblrig_local_data_path(subjects=False)
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)
        self.assertTrue(p.parts[-1] != "Subjects")

    def test_get_remote_server_data_path(self):
        # test without specifying subject arg
        p = path_helper.get_iblrig_remote_server_data_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)
        self.assertTrue(p.parts[-1] == "Subjects")

        # test specifying subject=True
        p = path_helper.get_iblrig_remote_server_data_path(subjects=True)
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)
        self.assertTrue(p.parts[-1] == "Subjects")

        # test specifying subject=False
        p = path_helper.get_iblrig_remote_server_data_path(subjects=False)
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)
        self.assertTrue(p.parts[-1] != "Subjects")

    def test_get_iblrig_path(self):
        p = path_helper.get_iblrig_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_iblrig_params_path(self):
        p = path_helper.get_iblrig_params_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_iblrig_temp_alyx_path(self):
        p = path_helper.get_iblrig_temp_alyx_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_iblrig_data_folder(self):
        df = path_helper.get_iblrig_data_folder(subjects=False)
        self.assertTrue(isinstance(df, str))
        self.assertTrue("iblrig_data" in df)
        self.assertTrue("Subjects" not in df)
        dfs = path_helper.get_iblrig_data_folder(subjects=True)
        self.assertTrue(isinstance(dfs, str))
        self.assertTrue("iblrig_data" in dfs)
        self.assertTrue("Subjects" in dfs)

    def test_get_commit_hash(self):
        import subprocess

        out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        # Run it
        ch = path_helper.get_commit_hash(str(path_helper.get_iblrig_path()))
        self.assertTrue(out == ch)

    def test_get_previous_session_folders(self):
        test_subject_name = "_iblrig_test_mouse"
        self.local_dir = tempfile.TemporaryDirectory()
        self.remote_dir = tempfile.TemporaryDirectory()

        def create_local_session():
            local_session_folder = (
                Path(self.local_dir.name) / "Subjects" / test_subject_name / "1900-01-01" / "001"
            )
            local_session_folder.mkdir(parents=True)
            return str(local_session_folder)

        def create_remote_subject():
            remote_subject_dir = Path(self.remote_dir.name) / "Subjects"
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
        test_previous_session_folders = path_helper.get_previous_session_folders(
            test_subject_name,
            test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder,
        )
        assert_values(test_previous_session_folders)

        # Test for an existing subject, local does exist and remote does NOT exist
        self.remote_dir.cleanup()
        # Call the function
        test_previous_session_folders = path_helper.get_previous_session_folders(
            test_subject_name,
            test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder,
        )
        assert_values(test_previous_session_folders)

        # Test for an existing subject, local does NOT exist and remote does exist
        self.local_dir.cleanup()
        test_remote_subject_folder = create_remote_subject()
        # Call the function
        test_previous_session_folders = path_helper.get_previous_session_folders(
            test_subject_name,
            test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder,
        )
        assert_values(test_previous_session_folders)

        # Test for an existing subject, local does NOT exist and remote does NOT exist
        self.local_dir.cleanup()
        self.remote_dir.cleanup()
        # Call the function
        test_previous_session_folders = path_helper.get_previous_session_folders(
            test_subject_name,
            test_local_session_folder,
            remote_subject_folder=test_remote_subject_folder,
        )
        assert_values(test_previous_session_folders)

        # Test for a new subject
        test_new_subject_name = "_new_iblrig_test_mouse"
        test_new_session_folder = (Path(self.local_dir.name) / "Subjects" / test_new_subject_name / "1970-01-01" / "001")
        test_previous_session_folders = path_helper.get_previous_session_folders(test_new_subject_name,
                                                                                 str(test_new_session_folder))
        self.assertTrue(isinstance(test_previous_session_folders, list))
        self.assertTrue(not test_previous_session_folders)  # returned list should be empty

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
