"""Tests for iblrig.path_helper module."""

import logging
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import yaml
from pydantic import BaseModel, ValidationError

import ibllib.tests.fixtures.utils as fu
from ibllib.tests import TEST_DB
from iblrig import path_helper
from iblrig.constants import HARDWARE_SETTINGS_YAML, RIG_SETTINGS_YAML
from iblrig.path_helper import load_pydantic_yaml, save_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings

TEST_ALYX_URL = TEST_DB['base_url']


class TestGetLocalAndRemotePaths(unittest.TestCase):
    def test_get_local_and_remote_paths(self):
        """Test iblrig.path_helper.get_local_and_remote_paths function."""
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        tmp = Path(tmpdir.name)
        tmp.joinpath('iblrigv8_data').mkdir()

        settings = dict(
            iblrig_local_data_path=tmp / 'iblrigv8_data',
            iblrig_remote_data_path=None,
            ALYX_USER='foo',
            ALYX_URL=TEST_ALYX_URL,
            ALYX_LAB='barlab',
        )
        iblrig_settings = RigSettings.model_validate(settings)
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        expected = {
            'local_subjects_folder': tmp / 'iblrigv8_data' / 'barlab' / 'Subjects',
            'remote_subjects_folder': None,
            **{k[7:-4] + 'folder': v for k, v in settings.items() if k.startswith('iblrig')},
        }
        self.assertDictEqual(expected, paths.model_dump())

        # Test lab arg
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings, lab='bazlab')
        self.assertEqual(tmp / 'iblrigv8_data' / 'bazlab' / 'Subjects', paths.local_subjects_folder)

        # Test no lab
        settings['ALYX_LAB'] = None
        iblrig_settings = RigSettings.model_validate(settings)
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        self.assertEqual(tmp / 'iblrigv8_data' / 'subjects', paths.local_subjects_folder)

        # Test Subjects already in local data path
        iblrig_settings = RigSettings.model_validate({**settings, 'iblrig_local_data_path': tmp / 'Subjects'})
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        self.assertEqual(paths.local_subjects_folder, paths.local_data_folder)

        # Test subjects path
        settings['iblrig_local_subjects_path'] = tmp / 'iblrigv8_data'
        iblrig_settings = RigSettings.model_validate(settings)
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        self.assertEqual(paths.local_subjects_folder, paths.local_data_folder)

        # Test remote data path
        settings['iblrig_remote_data_path'] = tmp / 'remote'
        iblrig_settings = RigSettings.model_validate(settings)
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        self.assertEqual(settings['iblrig_remote_data_path'], paths.remote_data_folder)
        self.assertEqual(tmp / 'remote' / 'Subjects', paths.remote_subjects_folder)

        # Test remote subjects path
        settings['iblrig_remote_data_path'] = tmp / 'remote' / 'Subjects'
        iblrig_settings = RigSettings.model_validate(settings)
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        self.assertEqual(settings['iblrig_remote_data_path'], paths.remote_data_folder)
        self.assertEqual(paths.remote_data_folder, paths.remote_subjects_folder)

        # Test iblrig_remote_subjects_path in settings
        settings['iblrig_remote_subjects_path'] = tmp / 'remote'
        iblrig_settings = RigSettings.model_validate(settings)
        paths = path_helper.get_local_and_remote_paths(iblrig_settings=iblrig_settings)
        self.assertNotEqual(paths.remote_subjects_folder, paths.remote_data_folder)
        self.assertEqual(settings['iblrig_remote_subjects_path'], paths.remote_subjects_folder)

        # Test paths args
        paths = path_helper.get_local_and_remote_paths(
            local_path=str(tmp / 'local'), remote_path=str(tmp / 'other'), iblrig_settings=iblrig_settings
        )
        self.assertEqual(tmp / 'other', paths.remote_data_folder)
        self.assertEqual(tmp / 'local', paths.local_data_folder)

    def test_no_settings_all_args_provided(self):
        """When iblrig_settings is None but all paths and lab are provided, settings are not loaded."""
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        tmp = Path(tmpdir.name)
        paths = path_helper.get_local_and_remote_paths(local_path=tmp / 'local', remote_path=tmp / 'remote', lab='testlab')
        self.assertEqual(tmp / 'local', paths.local_data_folder)
        self.assertEqual(tmp / 'remote', paths.remote_data_folder)

    def test_no_settings_loads_from_file(self):
        """When iblrig_settings is None and a path is missing, settings are loaded from file."""
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        tmp = Path(tmpdir.name)
        mock_settings = RigSettings.model_validate(
            {
                'iblrig_local_data_path': tmp / 'data',
                'iblrig_remote_data_path': None,
                'ALYX_USER': 'foo',
                'ALYX_URL': TEST_ALYX_URL,
                'ALYX_LAB': 'mocklab',
            }
        )
        with patch.object(path_helper, 'load_pydantic_yaml', return_value=mock_settings):
            paths = path_helper.get_local_and_remote_paths()
        self.assertEqual(tmp / 'data', paths.local_data_folder)


class TestIterateCollection(unittest.TestCase):
    """Test for iblrig.path_helper.iterate_collection"""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.session_path = Path(tmp.name)
        for collection in ('raw_task_data_foo', 'raw_task_data_00', 'raw_task_data_01', 'raw_foo_data_03', 'raw_bla_data_99'):
            self.session_path.joinpath(collection).mkdir()

    def test_iterate_collection(self):
        next_collection = path_helper.iterate_collection(self.session_path)
        self.assertEqual('raw_task_data_02', next_collection)
        next_collection = path_helper.iterate_collection('/non_existing_session')
        self.assertEqual('raw_task_data_00', next_collection)
        next_collection = path_helper.iterate_collection(self.session_path, 'raw_foo_data')
        self.assertEqual('raw_foo_data_04', next_collection)
        next_collection = path_helper.iterate_collection(self.session_path, 'raw_bar_data')
        self.assertEqual('raw_bar_data_00', next_collection)
        with self.assertRaises(ValueError):
            path_helper.iterate_collection(self.session_path, 'raw_bla_data')


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


class TestIteratePreviousSessions(unittest.TestCase):
    """Test for iblrig.path_helper.iterate_previous_sessions."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = Path(tmp.name)
        self.local_dir = self.tmpdir / 'local'
        self.remote_dir = self.tmpdir / 'remote'
        self.task = 'ephysCW'
        self.settings = {'NTRIALS': 260}

    def _create_session(self, root, date='1900-01-01', num='001', lab='fakelab'):
        sp = fu.create_fake_session_folder(root, date=date, num=num, lab=lab, increment=False)
        p = fu.create_fake_raw_behavior_data_folder(sp, task=self.task, folder='raw_task_data_00', write_pars_stub=True)
        fu.populate_task_settings(p, self.settings)
        return sp

    def test_local_only(self):
        """Sessions returned when no remote folder is configured."""
        self._create_session(self.local_dir, date='2024-01-01')
        self._create_session(self.local_dir, date='2024-01-02')
        sessions = path_helper.iterate_previous_sessions(
            'fakemouse',
            self.task,
            n=5,
            local_path=self.local_dir,
            remote_path=None,
            lab='fakelab',
            iblrig_settings={},
        )
        self.assertEqual(2, len(sessions))
        # Should be reverse chronological
        self.assertIn('2024-01-02', str(sessions[0]['session_path']))
        self.assertIn('2024-01-01', str(sessions[1]['session_path']))

    def test_n_limits_results(self):
        """At most n sessions are returned."""
        for d in ('2024-01-01', '2024-01-02', '2024-01-03'):
            self._create_session(self.local_dir, date=d)
        sessions = path_helper.iterate_previous_sessions(
            'fakemouse',
            self.task,
            n=2,
            local_path=self.local_dir,
            remote_path=None,
            lab='fakelab',
            iblrig_settings={},
        )
        self.assertEqual(2, len(sessions))

    def test_deduplication_local_and_remote(self):
        """Sessions present in both local and remote are deduplicated, local wins."""
        self._create_session(self.local_dir, date='2024-01-01')
        self._create_session(self.remote_dir, date='2024-01-01')
        sessions = path_helper.iterate_previous_sessions(
            'fakemouse',
            self.task,
            n=5,
            local_path=self.local_dir,
            remote_path=self.remote_dir / 'Subjects',
            lab='fakelab',
            iblrig_settings={},
        )
        self.assertEqual(1, len(sessions))
        self.assertIn('local', str(sessions[0]['session_path']))  # Local should win

    def test_merge_local_and_remote(self):
        """Unique sessions from local and remote are merged and sorted."""
        self._create_session(self.local_dir, date='2024-01-01')
        self._create_session(self.remote_dir, date='2024-01-02', lab='')
        sessions = path_helper.iterate_previous_sessions(
            'fakemouse',
            self.task,
            n=5,
            local_path=self.local_dir,
            remote_path=self.remote_dir / 'Subjects',
            lab='fakelab',
            iblrig_settings={},
        )
        self.assertEqual(2, len(sessions))
        self.assertIn('2024-01-02', str(sessions[0]['session_path']))
        self.assertIn('2024-01-01', str(sessions[1]['session_path']))

    def test_no_sessions(self):
        """Returns empty list when no matching sessions exist."""
        sessions = path_helper.iterate_previous_sessions(
            'fakemouse',
            self.task,
            n=5,
            local_path=self.local_dir,
            remote_path=None,
            lab='fakelab',
            iblrig_settings={},
        )
        self.assertEqual([], sessions)


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
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                save_pydantic_yaml(settings1, temp_file.name)
                with self.assertNoLogs(level=logging.ERROR):
                    settings2 = load_pydantic_yaml(model, temp_file.name)
                temp_file.file.close()
                os.unlink(temp_file.name)
            assert settings1 == settings2


class TestLoadSettingsYaml(unittest.TestCase):
    """Tests for iblrig.path_helper._load_settings_yaml."""

    def test_exception_do_raise_false(self):
        """When do_raise=False, exceptions are logged and an empty dict returned."""
        with self.assertLogs('iblrig.path_helper', level='ERROR'):
            result = path_helper._load_settings_yaml('/nonexistent/file.yaml', do_raise=False)
        self.assertEqual({}, result)

    def test_exception_do_raise_true(self):
        """When do_raise=True, exceptions propagate."""
        with self.assertRaises(FileNotFoundError):
            path_helper._load_settings_yaml('/nonexistent/file.yaml', do_raise=True)


class TestDeduceFilename(unittest.TestCase):
    """Tests for iblrig.path_helper._deduce_filename."""

    def test_hardware_settings(self):
        """HardwareSettings maps to HARDWARE_SETTINGS_YAML."""
        self.assertEqual(HARDWARE_SETTINGS_YAML, path_helper.deduce_settings_filename(HardwareSettings))

    def test_rig_settings(self):
        """RigSettings maps to RIG_SETTINGS_YAML."""
        self.assertEqual(RIG_SETTINGS_YAML, path_helper.deduce_settings_filename(RigSettings))

    def test_unknown_model_raises(self):
        """TypeError for unrecognised model type."""

        class Dummy(BaseModel):
            x: int = 1

        with self.assertRaises(TypeError):
            path_helper.deduce_settings_filename(Dummy)


class TestLoadPydanticYaml(unittest.TestCase):
    """Tests for iblrig.path_helper.load_pydantic_yaml."""

    def test_unknown_model_raises_type_error(self):
        """TypeError raised when model is not HardwareSettings or RigSettings and no filename given."""

        class Dummy(BaseModel):
            x: int = 1

        with self.assertRaises(TypeError):
            load_pydantic_yaml(Dummy)

    def test_validation_error_do_raise_false(self):
        """When do_raise=False, validation errors are logged and model_construct is used."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'INVALID_FIELD': 'bad_value'}, f)
            f.flush()
            fname = f.name
        self.addCleanup(lambda: os.unlink(fname))
        # Non-standard filename triggers do_raise=False internally
        with self.assertLogs('iblrig.path_helper', level='WARNING'):
            result = load_pydantic_yaml(HardwareSettings, fname)
        self.assertIsInstance(result, HardwareSettings)

    def test_validation_error_do_raise_true(self):
        """When do_raise=True and standard filename, ValidationError propagates."""
        with (
            patch('iblrig.path_helper._load_settings_yaml', return_value={'INVALID_FIELD': 'bad_value'}),
            patch('iblrig.path_helper.deduce_settings_filename', return_value=path_helper.HARDWARE_SETTINGS_YAML),
            self.assertRaises(ValidationError),
        ):
            load_pydantic_yaml(HardwareSettings)


class TestSavePydanticYaml(unittest.TestCase):
    """Tests for iblrig.path_helper.save_pydantic_yaml."""

    def test_unknown_model_raises_type_error(self):
        """TypeError raised when model instance is not HardwareSettings or RigSettings."""

        class Dummy(BaseModel):
            x: int = 1

        with self.assertRaises(TypeError):
            save_pydantic_yaml(Dummy(x=1))


class TestCreateBonsaiLayout(unittest.TestCase):
    """Tests for iblrig.path_helper.create_bonsai_layout_from_template."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = Path(tmp.name)

    def test_missing_workflow_raises(self):
        """FileNotFoundError when workflow file does not exist."""
        with self.assertRaises(FileNotFoundError):
            path_helper.create_bonsai_layout_from_template(self.tmpdir / 'missing.bonsai')

    def test_layout_created_from_template(self):
        """Layout file is created from template when it doesn't exist."""
        wf = self.tmpdir / 'workflow.bonsai'
        wf.touch()
        template = self.tmpdir / 'workflow.bonsai.layout_template'
        template.write_text('<Layout>test</Layout>')
        path_helper.create_bonsai_layout_from_template(wf)
        layout = self.tmpdir / 'workflow.bonsai.layout'
        self.assertTrue(layout.exists())
        self.assertEqual('<Layout>test</Layout>', layout.read_text())

    def test_existing_layout_not_overwritten(self):
        """Existing layout file is not overwritten."""
        wf = self.tmpdir / 'workflow.bonsai'
        wf.touch()
        layout = self.tmpdir / 'workflow.bonsai.layout'
        layout.write_text('existing')
        template = self.tmpdir / 'workflow.bonsai.layout_template'
        template.write_text('new')
        path_helper.create_bonsai_layout_from_template(wf)
        self.assertEqual('existing', layout.read_text())

    def test_no_template_available(self):
        """No error when neither layout nor template exist."""
        wf = self.tmpdir / 'workflow.bonsai'
        wf.touch()
        path_helper.create_bonsai_layout_from_template(wf)
        self.assertFalse((self.tmpdir / 'workflow.bonsai.layout').exists())


class TestProtocolNumber(unittest.TestCase):
    """Test the protocol_number inner function via _iterate_protocols."""

    def test_explicit_protocol_number_key(self):
        """When protocol_number key is present, it is used for sorting."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmpdir = Path(tmp.name)
        task = 'testTask'
        settings = {'NTRIALS': 260}

        sp = fu.create_fake_session_folder(tmpdir)
        # Create experiment description with explicit protocol_number
        stub = {
            'tasks': [
                {task: {'collection': 'raw_task_data_00', 'protocol_number': 5}},
                {task: {'collection': 'raw_task_data_01', 'protocol_number': 10}},
            ]
        }
        p0 = fu.create_fake_raw_behavior_data_folder(
            sp, task=task, folder='raw_task_data_00', write_pars_stub={'behaviour': stub}
        )
        fu.populate_task_settings(p0, settings)
        p1 = fu.create_fake_raw_behavior_data_folder(sp, task=task, folder='raw_task_data_01', write_pars_stub=False)
        fu.populate_task_settings(p1, settings)

        subject_folder = sp.parent.parent
        results = path_helper._iterate_protocols(subject_folder, task, n=1)
        # Should pick the one with higher protocol_number (raw_task_data_01, pn=10)
        self.assertEqual(1, len(results))
        self.assertEqual('raw_task_data_01', results[0]['task_collection'])


if __name__ == '__main__':
    unittest.main(exit=False)
