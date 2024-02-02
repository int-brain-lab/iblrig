"""Tests for iblrig.path_helper module."""
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy

from iblrig import path_helper
from iblrig.constants import BASE_DIR
from iblrig.pydantic_definitions import HardwareSettings


class TestPathHelper(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_commit_hash(self):
        import subprocess

        out = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
        # Run it
        ch = path_helper.get_commit_hash(BASE_DIR)
        self.assertTrue(out == ch)

    def tearDown(self):
        pass


class TestIterateCollection(unittest.TestCase):
    """Test for iblrig.path_helper.iterate_collection"""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.session_path = Path(tmp.name)
        for collection in ('raw_task_data_foo', 'raw_task_data_00', 'raw_task_data_01', 'raw_foo_data_03'):
            self.session_path.joinpath(collection).mkdir()

    def test_iterate_collection(self):
        next_collection = path_helper.iterate_collection(str(self.session_path))
        self.assertEqual('raw_task_data_02', next_collection)
        next_collection = path_helper.iterate_collection('/non_existing_session')
        self.assertEqual('raw_task_data_00', next_collection)
        next_collection = path_helper.iterate_collection(str(self.session_path), 'raw_foo_data')
        self.assertEqual('raw_foo_data_04', next_collection)
        next_collection = path_helper.iterate_collection(str(self.session_path), 'raw_bar_data')
        self.assertEqual('raw_bar_data_00', next_collection)


class TestPatchSettings(unittest.TestCase):
    """Test for iblrig.path_helper.patch_settings."""

    def test_patch_hardware_settings(self):
        recording_workflow = 'devices/camera_recordings/TrainingRig_SaveVideo_TrainingTasks.bonsai'
        setup_workflow = 'devices/camera_setup/setup_video.bonsai'
        # Version 0 settings example
        rs = {'RIG_NAME': 'foo_rig', 'MAIN_SYNC': True, 'device_camera': {'BONSAI_WORKFLOW': recording_workflow}}
        updated = path_helper.patch_settings(deepcopy(rs), 'hardware_settings')
        self.assertEqual('1.1.0', updated.get('VERSION'))
        self.assertNotIn('device_camera', updated)
        expected = {'BONSAI_WORKFLOW': {'setup': setup_workflow, 'recording': recording_workflow},
                    'left': {'INDEX': 1, 'SYNC_LABEL': 'audio'}}
        self.assertEqual(expected, updated.get('device_cameras', {}).get('training'))
        # HardwareSettings.model_validate(updated)  # Should pass validation?
        HardwareSettings.validate_device_cameras(updated['device_cameras'])
        # Assert unchanged when all up to date
        self.assertDictEqual(path_helper.patch_settings(deepcopy(updated), 'hardware_settings'), updated)
        # Test v1.0 -> v1.1
        v1 = deepcopy(rs)
        # Some settings files have empty camera fields
        v1['device_cameras'] = {'left': {'BONSAI_WORKFLOW': recording_workflow}, 'right': None, 'body': None}
        v1['VERSION'] = '1.0.0'
        v2 = path_helper.patch_settings(v1, 'hardware_settings')
        self.assertEqual('1.1.0', v2.get('VERSION'))
        self.assertEqual(expected, v2.get('device_cameras', {}).get('training'))
        HardwareSettings.validate_device_cameras(v2['device_cameras'])
        # Test without any device_cameras key (should be optional)
        rs.pop('device_camera')
        self.assertIn('device_cameras', path_helper.patch_settings(rs, 'hardware_settings'))
        HardwareSettings.validate_device_cameras({})


if __name__ == '__main__':
    unittest.main(exit=False)
