"""Tests for iblrig.path_helper module."""
import tempfile
import unittest
from pathlib import Path

import ibllib.tests.fixtures.utils as fu
from iblrig import path_helper
from iblrig.base_tasks import BonsaiRecordingMixin
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


class TestIterateProtocols(unittest.TestCase):
    """Test for iblrig.path_helper._iterate_protocols."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = Path(tmp.name)
        self.session_paths = [fu.create_fake_session_folder(self.tmpdir) for _ in range(3)]
        self.session_paths.append(fu.create_fake_session_folder(self.tmpdir, date='1900-01-02'))

    def test_iterate_protocols(self):
        task = 'ephysCW'
        self.settings = {'NTRIALS': 260}
        # First session has it all
        p = fu.create_fake_raw_behavior_data_folder(
            self.session_paths[0], task=task, folder='raw_task_data_00', write_pars_stub=True
        )
        fu.populate_task_settings(p, self.settings)

        # Second session has no settings file
        p = fu.create_fake_raw_behavior_data_folder(
            self.session_paths[1], task=task, folder='raw_task_data_00', write_pars_stub=True
        )
        p.joinpath('_iblrig_taskSettings.raw.json').unlink()

        # Third has two chained protocols
        stub = {
            'tasks': [
                {'ephysCW': {'collection': 'raw_task_data_00'}},
                {'passiveCW': {'collection': 'raw_task_data_01'}},
                {'ephysCW': {'collection': 'raw_task_data_02'}},
            ]
        }
        p = fu.create_fake_raw_behavior_data_folder(
            self.session_paths[2], task=task, folder='raw_task_data_00', write_pars_stub={'behaviour': stub}
        )
        fu.populate_task_settings(p, self.settings)
        fu.create_fake_raw_behavior_data_folder(
            self.session_paths[2], task='passiveCW', folder='raw_task_data_01', write_pars_stub=False
        )
        p = fu.create_fake_raw_behavior_data_folder(
            self.session_paths[2], task='ephysCW', folder='raw_task_data_02', write_pars_stub=False
        )
        fu.populate_task_settings(p, self.settings)

        # Forth has different task
        p = fu.create_fake_raw_behavior_data_folder(
            self.session_paths[3], task='foobarCW', folder='raw_task_data_00', write_pars_stub=True
        )
        fu.populate_task_settings(p, self.settings)

        # Filter by task name
        subject_folder = self.tmpdir / 'fakelab' / 'Subjects' / 'fakemouse'
        last_valid = path_helper._iterate_protocols(subject_folder, task)
        self.assertEqual(1, len(last_valid), 'failed to return any protocols')
        self.assertEqual(self.session_paths[2], last_valid[0]['session_path'])
        self.assertEqual('raw_task_data_02', last_valid[0]['task_collection'])
        self.assertEqual(self.settings['NTRIALS'], last_valid[0]['task_settings'].get('NTRIALS'))
        # Filter by min trials
        last_valid = path_helper._iterate_protocols(subject_folder, task, min_trials=300)
        self.assertEqual(0, len(last_valid))
        # Filter by different task name
        last_valid = path_helper._iterate_protocols(subject_folder, 'foobarCW')
        self.assertEqual(1, len(last_valid))
        self.assertEqual(self.session_paths[-1], last_valid[0]['session_path'])
        # Return for multiple protocols
        last_valid = path_helper._iterate_protocols(subject_folder, task, n=4)
        self.assertEqual(3, len(last_valid), 'failed to return any protocols')
        self.assertEqual(self.session_paths[0], last_valid[-1]['session_path'])
        # Should return None when session missing
        subject_folder = subject_folder.with_name('foo')
        self.assertEqual([], path_helper._iterate_protocols(subject_folder, task))


class TestPatchSettings(unittest.TestCase):
    """Test for iblrig.path_helper.patch_settings"""

    def test_patch_hardware_settings(self):
        rs = {'RIG_NAME': 'foo_rig', 'MAIN_SYNC': True, 'device_camera': {'BONSAI_WORKFLOW': 'path/to/Workflow.bonsai'}}
        updated = path_helper.patch_settings(rs.copy(), 'hardware_settings')
        self.assertEqual('1.0.0', updated.get('VERSION'))
        self.assertNotIn('device_camera', updated)
        self.assertEqual(rs['device_camera'], updated.get('device_cameras', {}).get('left'))
        self.assertDictEqual(path_helper.patch_settings(updated.copy(), 'hardware_settings'), updated)


class TestHardwareSettings(unittest.TestCase):
    def test_get_left_camera_workflow(self):
        hws = path_helper.load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        self.assertIsNotNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file(hws['device_cameras']))
        self.assertIsNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file(None))
        self.assertIsNone(BonsaiRecordingMixin._camera_mixin_bonsai_get_workflow_file({}))


if __name__ == '__main__':
    unittest.main(exit=False)
