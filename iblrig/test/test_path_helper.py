"""Tests for iblrig.path_helper module."""
import logging
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

import ibllib.tests.fixtures.utils as fu
from iblrig import path_helper
from iblrig.constants import BASE_DIR
from iblrig.path_helper import load_pydantic_yaml, save_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings


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
    """Test for iblrig.path_helper.patch_settings."""

    def setUp(self):
        file = Path(__file__).parents[2].joinpath('settings', 'hardware_settings_template.yaml')
        with open(file) as fp:
            self.rs = yaml.safe_load(fp)
        self.rs.pop('device_cameras')

    def test_patch_hardware_settings(self):
        recording_workflow = 'devices/camera_recordings/TrainingRig_SaveVideo_TrainingTasks.bonsai'
        setup_workflow = 'devices/camera_setup/setup_video.bonsai'
        # Version 0 settings example
        # rs = {'RIG_NAME': 'foo_rig', 'MAIN_SYNC': True,
        rs = deepcopy(self.rs)
        rs['VERSION'] = '0.1.0'
        rs['device_camera'] = {'BONSAI_WORKFLOW': recording_workflow}
        updated = path_helper.patch_settings(rs, 'hardware_settings')
        self.assertEqual('1.1.0', updated.get('VERSION'))
        self.assertNotIn('device_camera', updated)
        expected = {
            'BONSAI_WORKFLOW': {'setup': setup_workflow, 'recording': recording_workflow},
            'left': {'INDEX': 1, 'SYNC_LABEL': 'audio'},
        }
        self.assertEqual(expected, updated.get('device_cameras', {}).get('training'))
        HardwareSettings.model_validate(updated)  # Should pass validation?
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
        HardwareSettings.model_validate(v2)
        # Test without any device_cameras key (should be optional)
        rs.pop('device_cameras')
        self.assertIn('device_cameras', path_helper.patch_settings(rs, 'hardware_settings'))
        rs['device_cameras'] = None
        self.assertEqual(path_helper.patch_settings(rs, 'hardware_settings').get('device_cameras'), {})
        HardwareSettings.model_validate(rs)  # Test model validation when device_cameras is empty dict


class TestYAML(unittest.TestCase):
    def test_yaml_roundtrip(self):
        for model, filename in [
            (HardwareSettings, 'hardware_settings_template.yaml'),
            (RigSettings, 'iblrig_settings_template.yaml'),
        ]:
            with self.assertNoLogs(level=logging.ERROR):
                settings1 = load_pydantic_yaml(model, filename)
            with tempfile.NamedTemporaryFile(mode='w') as temp_file:
                save_pydantic_yaml(settings1, temp_file.name)
                with self.assertNoLogs(level=logging.ERROR):
                    settings2 = load_pydantic_yaml(model, temp_file.name)
            assert settings1 == settings2


if __name__ == '__main__':
    unittest.main(exit=False)
