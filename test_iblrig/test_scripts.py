import tempfile
import unittest
from pathlib import Path

from one.api import ONE

from scripts.ibllib.purge_rig_data import purge_local_data, session_name
from test_iblrig import OPENALYX_PARAMETERS


class TestScripts(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def test_purge_rig_data(self):
        # Setup out test
        root = Path(self.tempdir.name)
        local_data = root.joinpath('iblrig_data', 'Subjects')
        local_data.mkdir(parents=True)
        # Need to add a username/password to the ONE call for the test to function
        one = ONE(**OPENALYX_PARAMETERS)
        # Find a session with at least 5 or so datasets and touch those files
        sessions = one.search(lab='cortex')
        session = next(x for x in sessions if len(one.list_datasets(x, collection='raw*')) > 5)
        session_path = local_data.joinpath(session_name(one.eid2path(session)))
        datasets = one.list_datasets(session_path, collection='raw*')
        for rel_path in datasets:
            session_path.joinpath(rel_path).parent.mkdir(parents=True, exist_ok=True)
            session_path.joinpath(rel_path).touch()
        # Touch some files that don't exist in the cache
        session_path.joinpath('raw_foobar_data').mkdir()
        for i in range(5):
            session_path.joinpath('raw_foobar_data', f'_test_foo.bar{i}.npy').touch()

        # Test filename filter
        filename = '*' + '.'.join(datasets[0].split('.', 2)[:-1]) + '.*'  # e.g. *foo/bar.baz.*
        assert any(session_path.rglob(filename))  # Files matching pattern should exist
        # Dry run first, no files should be effected
        removed = purge_local_data(str(local_data), filename, one=one, dry=True)
        self.assertTrue(
            all(session_path.rglob(filename)), 'files matching pattern deleted on dry run'
        )
        self.assertFalse(
            any(not x.exists() for x in removed), 'files matching pattern deleted on dry run'
        )
        removed = purge_local_data(str(local_data), filename, one=one, dry=False)
        self.assertFalse(
            any(session_path.rglob(filename)), 'files matching pattern were not removed'
        )
        self.assertFalse(any(x.exists() for x in removed), 'some returned files were not unlinked')
        # Other registered datasets should still exist
        self.assertTrue(any(x for x in session_path.rglob('*.*') if 'foobar' not in str(x)))

        # Test purge all
        removed = purge_local_data(str(local_data), one=one)
        self.assertFalse(any(x.exists() for x in removed), 'some returned files were not unlinked')
        self.assertFalse(
            any('foobar' in x for x in map(str, removed)), "files deleted that weren't in cache"
        )

    def test_transfer_rig_data(self):
        # Ensure transfer_rig_data.py exists in the location we expect it
        current_path = Path(__file__).parent.absolute()
        transfer_rig_data_script_loc = current_path.parent / 'scripts' / 'transfer_rig_data.py'
        self.assertTrue(transfer_rig_data_script_loc.exists())

        # Tests below will only pass if the call to 'move_ephys.py' script is commented out in
        # 'transfer_rig_data.py' main
        # Create local and remote temp directories, local session path, flags, and taskSettings
        # local_temp_dir = tempfile.TemporaryDirectory()
        # remote_temp_dir = tempfile.TemporaryDirectory()
        # local_subjects_dir = pathlib.Path(local_temp_dir.name) / 'Subjects'
        # remote_subjects_dir = pathlib.Path(remote_temp_dir.name) / 'Subjects'
        # local_session_location = pathlib.Path(local_subjects_dir) \
        #                          / '_iblrig_fake_mouse' / '1970-01-01' / '001'
        # local_raw_video_location = pathlib.Path(local_session_location) / 'raw_video_data'
        # local_raw_behavior_location = pathlib.Path(local_session_location) / 'raw_behavior_data'
        # task_settings_data = {'PYBPOD_BOARD': '_iblrig_mainenlab_behavior_2'}
        # try:
        #     # add passive ephys data
        #     os.makedirs(local_subjects_dir, exist_ok=True)
        #     os.makedirs(remote_subjects_dir, exist_ok=True)
        #     os.makedirs(local_session_location, exist_ok=True)
        #     os.makedirs(local_raw_video_location, exist_ok=True)
        #     os.makedirs(local_raw_behavior_location, exist_ok=True)
        #     local_session_location.joinpath('transfer_me.flag').touch()
        #     local_raw_video_location.joinpath('_iblrig_leftCamera.raw.avi').touch()
        #     local_raw_behavior_location.joinpath('_iblrig_micData.raw.wav').touch()
        #     with open(local_raw_behavior_location / '_iblrig_taskSettings.raw.json', 'w') \
        #             as task_settings:
        #         json.dump(task_settings_data, task_settings)
        # except OSError:
        #     print('Could not create temp directories and/or flag files.')
        #
        # # Call transfer_rig_data.py script
        # os.system(f"python "
        #           f"{transfer_rig_data_script_loc} {local_subjects_dir} {remote_subjects_dir}")
        #
        # # verify files moved
        # remote_session_location = pathlib.Path(remote_subjects_dir) \
        #                           / '_iblrig_fake_mouse' / '1970-01-01' / '001'
        # remote_raw_video_location = pathlib.Path(remote_session_location) / 'raw_video_data'
        # remote_raw_video_left_camera = pathlib.Path(remote_raw_video_location) \
        #                                / '_iblrig_leftCamera.raw.avi'
        # remote_raw_behavior_location = pathlib.Path(remote_session_location) / 'raw_behavior_data'
        # remote_raw_behavior_mic_data = pathlib.Path(remote_raw_behavior_location) \
        #                                / '_iblrig_micData.raw.wav'
        # remote_raw_session_flag = pathlib.Path(remote_session_location) / 'raw_session.flag'
        # self.assertTrue(remote_raw_video_left_camera.exists())
        # self.assertTrue(remote_raw_behavior_mic_data.exists())
        # self.assertTrue(remote_raw_session_flag.exists())
        #
        #
        # Tests below need to be fully fleshed out
        # Test for ephys rig, generate _iblrig_taskSettings.raw.json
        # task_settings_data = {'PYBPOD_BOARD': '_iblrig_mainenlab_ephys_0'}
        # try:
        #     with open(local_raw_behavior_location / '_iblrig_taskSettings.raw.json', 'w') \
        #             as task_settings:
        #         json.dump(task_settings_data, task_settings)
        # except OSError:
        #     print('Could not create json files')
        #
        # # Verify raw_session.flag file was removed
        # # log.info(f"Removing raw_session.flag file; ephys behavior rig detected")
        #
        # # Cleanup of temp directories and files
        # local_temp_dir.cleanup()
        # remote_temp_dir.cleanup()
