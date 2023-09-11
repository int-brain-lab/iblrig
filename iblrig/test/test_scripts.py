import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from one.api import ONE

import scripts.transfer_rig_data as transfer_rig_data
from scripts.ibllib.purge_rig_data import purge_local_data, session_name
from ibllib.tests import TEST_DB


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
        one = ONE(**TEST_DB)
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
        # Create parent temp directories
        temp_dir = tempfile.TemporaryDirectory()
        local_subjects_dir = Path(temp_dir.name) / "local" / "Subjects"
        remote_subjects_dir = Path(temp_dir.name) / "remote" / "Subjects"
        os.makedirs(local_subjects_dir)
        os.makedirs(remote_subjects_dir)

        # Behavior Rig running behavior task - directory creation and flag files
        local_session_dir = local_subjects_dir / "_iblrig_fake_mouse" / "1970-01-01" / "001"
        local_raw_video_dir = local_session_dir / "raw_video_data"
        local_raw_behavior_dir = local_session_dir / "raw_behavior_data"
        os.makedirs(local_raw_video_dir)
        os.makedirs(local_raw_behavior_dir)
        Path(local_session_dir / "transfer_me.flag").touch()
        Path(local_raw_video_dir / "_iblrig_leftCamera.raw.avi").touch()
        Path(local_raw_behavior_dir / "_iblrig_micData.raw.wav").touch()
        task_settings_data = {"PYBPOD_BOARD": "_iblrig_mainenlab_behavior_2"}
        with open(local_raw_behavior_dir / "_iblrig_taskSettings.raw.json", "w") as task_settings:
            json.dump(task_settings_data, task_settings)
        transfer_rig_data.main(str(local_subjects_dir), str(remote_subjects_dir))  # Call transfer script
        # verify files moved to remote location
        remote_session_dir = remote_subjects_dir / "_iblrig_fake_mouse" / "1970-01-01" / "001"
        remote_raw_video_dir = remote_session_dir / "raw_video_data"
        remote_raw_video_left_camera = remote_raw_video_dir / "_iblrig_leftCamera.raw.avi"
        remote_raw_behavior_dir = remote_session_dir / "raw_behavior_data"
        remote_raw_behavior_mic_data = remote_raw_behavior_dir / "_iblrig_micData.raw.wav"
        remote_raw_session_flag = remote_session_dir / "raw_session.flag"
        self.assertTrue(remote_raw_video_left_camera.exists())
        self.assertTrue(remote_raw_behavior_mic_data.exists())
        self.assertTrue(remote_raw_session_flag.exists())
        shutil.rmtree(local_subjects_dir / "_iblrig_fake_mouse")  # Behavior rig clean up
        shutil.rmtree(remote_subjects_dir / "_iblrig_fake_mouse")

        # Ephys Rig running behavior task - directory creation and flag files
        local_session_dir = local_subjects_dir / "_iblrig_fake_mouse" / "1970-01-01" / "001"
        local_raw_video_dir = local_session_dir / "raw_video_data"
        local_raw_behavior_dir = local_session_dir / "raw_behavior_data"
        os.makedirs(local_raw_video_dir)
        os.makedirs(local_raw_behavior_dir)
        Path(local_session_dir / "transfer_me.flag").touch()
        Path(local_raw_video_dir / "_iblrig_leftCamera.raw.avi").touch()
        Path(local_raw_behavior_dir / "_iblrig_micData.raw.wav").touch()
        task_settings_data = {"PYBPOD_BOARD": "_iblrig_mainenlab_ephys_2"}
        with open(local_raw_behavior_dir / "_iblrig_taskSettings.raw.json", "w") as task_settings:
            json.dump(task_settings_data, task_settings)
        transfer_rig_data.main(str(local_subjects_dir), str(remote_subjects_dir))  # Call transfer script
        # verify files moved to remote location
        remote_session_dir = remote_subjects_dir / "_iblrig_fake_mouse" / "1970-01-01" / "001"
        remote_raw_video_dir = remote_session_dir / "raw_video_data"
        remote_raw_video_left_camera = remote_raw_video_dir / "_iblrig_leftCamera.raw.avi"
        remote_raw_behavior_dir = remote_session_dir / "raw_behavior_data"
        remote_raw_behavior_mic_data = remote_raw_behavior_dir / "_iblrig_micData.raw.wav"
        remote_raw_session_flag = remote_session_dir / "raw_session.flag"
        self.assertTrue(remote_raw_video_left_camera.exists())
        self.assertTrue(remote_raw_behavior_mic_data.exists())
        self.assertFalse(remote_raw_session_flag.exists())  # raw_session_flag should get removed by transfer script
        shutil.rmtree(local_subjects_dir / "_iblrig_fake_mouse")  # Ephys rig clean up
        shutil.rmtree(remote_subjects_dir / "_iblrig_fake_mouse")

        # Temp dir cleanup
        shutil.rmtree(Path(temp_dir.name))
