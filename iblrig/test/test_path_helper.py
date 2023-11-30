"""Tests for iblrig.path_helper module."""
import tempfile
import unittest
from pathlib import Path

import iblrig.path_helper
from iblrig.base_tasks import BonsaiRecordingMixin


class TestPathHelper(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_iblrig_path(self):
        p = iblrig.path_helper.get_iblrig_path()
        self.assertIsNotNone(p)
        self.assertIsInstance(p, Path)

    def test_get_commit_hash(self):
        import subprocess

        out = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
        # Run it
        ch = iblrig.path_helper.get_commit_hash(str(iblrig.path_helper.get_iblrig_path()))
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
        next_collection = iblrig.path_helper.iterate_collection(str(self.session_path))
        self.assertEqual('raw_task_data_02', next_collection)
        next_collection = iblrig.path_helper.iterate_collection('/non_existing_session')
        self.assertEqual('raw_task_data_00', next_collection)
        next_collection = iblrig.path_helper.iterate_collection(str(self.session_path), 'raw_foo_data')
        self.assertEqual('raw_foo_data_04', next_collection)
        next_collection = iblrig.path_helper.iterate_collection(str(self.session_path), 'raw_bar_data')
        self.assertEqual('raw_bar_data_00', next_collection)


class TestPatchSettings(unittest.TestCase):
    """Test for iblrig.path_helper.patch_settings"""

    def test_patch_hardware_settings(self):
        rs = {'RIG_NAME': 'foo_rig', 'MAIN_SYNC': True, 'device_camera': {'BONSAI_WORKFLOW': 'path/to/Workflow.bonsai'}}
        updated = iblrig.path_helper.patch_settings(rs.copy(), 'hardware_settings')
        self.assertEqual('1.0.0', updated.get('VERSION'))
        self.assertNotIn('device_camera', updated)
        self.assertEqual(rs['device_camera'], updated.get('device_cameras', {}).get('left'))
        self.assertDictEqual(iblrig.path_helper.patch_settings(updated.copy(), 'hardware_settings'), updated)


class TestHardwareSettings(unittest.TestCase):
    def test_get_left_camera_workflow(self):
        hws = iblrig.path_helper.load_settings_yaml('hardware_settings_template.yaml')
        self.assertIsNotNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file(hws['device_cameras']))
        self.assertIsNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file(None))
        self.assertIsNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file({}))


if __name__ == '__main__':
    unittest.main(exit=False)
