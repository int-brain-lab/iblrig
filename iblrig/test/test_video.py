import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np
import yaml

from iblutil.util import Bunch

"""In order to mock iblrig.video_pyspin.enable_camera_trigger we must mock PySpin here."""
sys.modules['PySpin'] = MagicMock()

from iblrig import video  # noqa
from iblrig.path_helper import load_pydantic_yaml, HARDWARE_SETTINGS_YAML, RIG_SETTINGS_YAML  # noqa
from iblrig.pydantic_definitions import HardwareSettings  # noqa


class TestDownloadFunction(unittest.TestCase):
    @patch('iblrig.video.aws.s3_download_file', return_value=Path('mocked_tmp_file'))
    @patch('iblrig.video.hashfile.md5', return_value='mocked_md5_checksum')
    @patch('os.rename', return_value=None)
    def test_download_from_alyx_or_flir(self, mock_os_rename, mock_hashfile, mock_aws_download):
        asset = 123
        filename = 'test_file.txt'

        # Call the function
        result = video._download_from_alyx_or_flir(asset, filename, 'mocked_md5_checksum')

        # Assertions
        expected_out_file = Path.home().joinpath('Downloads', filename)
        self.assertEqual(result, expected_out_file)
        mock_hashfile.assert_called()
        mock_aws_download.assert_called_once_with(source=f'resources/{filename}', destination=Path(expected_out_file))
        mock_os_rename.assert_called_once_with(Path('mocked_tmp_file'), expected_out_file)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.old_params = Bunch(
            {
                'DATA_FOLDER_PATH': r'D:\iblrig_data\Subjects',
                'REMOTE_DATA_FOLDER_PATH': r'\\iblserver.champalimaud.pt\ibldata\Subjects',
                'BODY_CAM_IDX': 0,
                'LEFT_CAM_IDX': 3,
                'RIGHT_CAM_IDX': 2,
            }
        )
        params_dict_mock = patch('iblrig.video.load_params_dict', return_value=self.old_params)
        params_dict_mock.start()
        self.addCleanup(params_dict_mock.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Some dummy files to open
        for name in ('hardware_settings', 'iblrig_settings'):
            (file := Path(self.tmp.name, name + '.yaml')).touch()
            m = patch(f'iblrig.video.{name.replace("ibl", "").upper()}_YAML', file)
            m.start()
            self.addCleanup(m.stop)

        self._settings = {}  # Store the unpatched settings (we'll use the template ones)
        self.patched = {}  # Store the patched settings
        for file in ('iblrig', 'hardware'):
            filepath = Path(video.__file__).parents[1].joinpath('settings', f'{file}_settings_template.yaml')
            if filepath.exists():
                with open(filepath) as fp:
                    self._settings[file] = yaml.safe_load(fp.read())

    def _return_settings(self, fp) -> dict:
        """Return settings dict when yaml.safe_load mock called."""
        return self._settings['hardware' if 'hardware' in Path(fp.name).name else 'iblrig']

    @patch('iblrig.video.params.getfile')
    @patch('iblrig.video.yaml.safe_dump')
    @patch('iblrig.video.yaml.safe_load')
    def test_patch_old_params(self, safe_load_mock, safe_dump_mock, getfile_mock):
        """Test iblrig.video.patch_old_params function."""
        (old_file := Path(self.tmp.name, '.videopc_params')).touch()
        safe_load_mock.side_effect = self._return_settings
        safe_dump_mock.side_effect = self._store_patched_settings
        self._settings['hardware']['device_cameras']['ephys'] = {'left': {}, 'right': {'FPS': 150}, 'body': {}, 'belly': {}}
        getfile_mock.return_value = old_file
        video.patch_old_params(remove_old=False)

        # Check the patched hardware settings
        patched = self.patched['hardware']
        self.assertIn('device_cameras', patched)
        for cam, idx in dict(left=3, right=2, body=0).items():
            self.assertEqual(idx, patched['device_cameras']['ephys'][cam]['INDEX'])
        self.assertEqual(3, self._settings['hardware']['device_cameras']['default']['left']['INDEX'])
        # Check irrelevant fields unmodified
        self.assertNotIn('right', self._settings['hardware']['device_cameras']['default'])
        self.assertIn('belly', self._settings['hardware']['device_cameras']['ephys'])

        # Check the patched iblrig settings
        patched = self.patched['iblrig']
        self.assertEqual(r'D:\iblrig_data', patched['iblrig_local_data_path'])
        self.assertEqual(r'\\iblserver.champalimaud.pt\ibldata', patched['iblrig_remote_data_path'])
        self.assertTrue(old_file.exists(), 'failed to keep old settings file')

        # Test insertion of 'subjects' path key if old location doesn't end in 'Subjects'
        for key in ('DATA_FOLDER_PATH', 'REMOTE_DATA_FOLDER_PATH'):
            self.old_params[key] = self.old_params[key].replace('Subjects', 'foobar')
        with (
            patch('iblrig.video.HARDWARE_SETTINGS_YAML', Path(self.tmp.name, 'na')),
            patch('iblrig.video.RIG_SETTINGS_YAML', Path(self.tmp.name, 'na')),
        ):
            # Check this works without settings files
            video.patch_old_params(remove_old=True)
        patched = self.patched['iblrig']  # Load the patched settings
        self.assertEqual(self.old_params['DATA_FOLDER_PATH'], patched['iblrig_local_subjects_path'])
        self.assertEqual(self.old_params['REMOTE_DATA_FOLDER_PATH'], patched['iblrig_remote_subjects_path'])
        self.assertFalse(old_file.exists(), 'failed to remove old settings file')

        video.patch_old_params()  # Shouldn't raise after removing old settings

    def _store_patched_settings(self, settings, fp):
        """Store settings passed to yaml.safe_dump mock."""
        key = 'hardware' if 'hardware' in Path(fp.name).name else 'iblrig'
        self.patched[key] = settings


class TestPrepareVideoSession(unittest.TestCase):
    """Test for iblrig.video.prepare_video_session."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.subject = 'foobar'
        self.addCleanup(self.tmp.cleanup)
        (input_mock := patch('builtins.input')).start()
        self.addCleanup(input_mock.stop)

    @patch('iblrig.video.EmptySession')
    @patch('iblrig.video.HAS_PYSPIN', True)
    @patch('iblrig.video.HAS_SPINNAKER', True)
    @patch('iblrig.video.call_bonsai')
    @patch('iblrig.video_pyspin.enable_camera_trigger')
    def test_prepare_video_session(self, enable_camera_trigger, call_bonsai, session):
        """Test iblrig.video.prepare_video_session function."""
        # Set up mock session folder
        session_path = Path(self.tmp.name, self.subject, '2020-01-01', '001')
        session().paths.SESSION_FOLDER = session_path
        session_path.mkdir(parents=True)
        # Set up remote path
        remote_path = Path(self.tmp.name, 'remote', self.subject, '2020-01-01', '001')
        session().paths.REMOTE_SUBJECT_FOLDER = remote_path
        remote_path.mkdir(parents=True)
        # Some test hardware settings
        hws = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        hws['device_cameras']['default']['right'] = hws['device_cameras']['default']['left']
        session().hardware_settings = hws
        workflows = hws['device_cameras']['default']['BONSAI_WORKFLOW']

        video.prepare_video_session(self.subject, 'default')

        # Validate calls
        expected = [call(enable=False), call(enable=True), call(enable=False)]
        enable_camera_trigger.assert_has_calls(expected)
        raw_data_folder = session_path / 'raw_video_data'
        expected_pars = {
            'LeftCameraIndex': 1,
            'RightCameraIndex': 1,
            'FileNameLeft': str(raw_data_folder / '_iblrig_leftCamera.raw.avi'),
            'FileNameLeftData': str(raw_data_folder / '_iblrig_leftCamera.frameData.bin'),
            'FileNameRight': str(raw_data_folder / '_iblrig_rightCamera.raw.avi'),
            'FileNameRightData': str(raw_data_folder / '_iblrig_rightCamera.frameData.bin'),
        }
        expected = [call(workflows.setup, ANY, debug=False), call(workflows.recording, expected_pars, wait=False, debug=False)]
        call_bonsai.assert_has_calls(expected)

        # Test config validation
        self.assertRaises(ValueError, video.prepare_video_session, self.subject, 'training')
        session().hardware_settings = hws.model_construct()
        self.assertRaises(ValueError, video.prepare_video_session, self.subject, 'training')


class TestValidateVideo(unittest.TestCase):
    """Test for iblrig.video.validate_video."""

    def setUp(self):
        hws = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        self.config = hws['device_cameras']['default']['left']
        self.meta = Bunch(length=1000, fps=30, height=1024, width=1280, duration=timedelta(seconds=1000 * 30))
        self.count = np.arange(self.meta['length'])
        n = 300  # The number of GPIO events
        pin = {'indices': np.round(np.linspace(0, self.count.size, n)), 'polarities': np.ones(n)}
        self.gpio = [None, None, None, pin]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.video_path = Path(tmp.name).joinpath('subject', '2020-01-01', '001', 'raw_video_data', '_iblrig_leftCamera.raw.avi')
        self.video_path.parent.mkdir(parents=True)
        with open(self.video_path, 'wb') as fp:
            np.save(fp, self.count)  # ensure raw video not 0 bytes

    @patch('iblrig.video.get_video_meta')
    @patch('iblrig.video.load_embedded_frame_data')
    def test_validate_video(self, load_embedded_frame_data, get_video_meta):
        """Test iblrig.video.validate_video function."""
        get_video_meta.return_value = self.meta
        load_embedded_frame_data.return_value = (self.count, self.gpio)
        # Test everything in order
        with self.assertLogs(video.__name__, 20) as log:
            self.assertTrue(video.validate_video(self.video_path, self.config))
            expected = {
                'Checking left camera for session 2020-01-01_001_subject',
                '300 event(s) on GPIO #4',
                'Duration = 30000.00',
                'N frames = 1000',
            }
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)
        # Test video meta warnings
        config = self.config.model_copy()
        config.HEIGHT = config.WIDTH = 160
        config.FPS = 150
        with self.assertLogs(video.__name__, 30) as log:
            self.assertFalse(video.validate_video(self.video_path, config))
            expected = {'Frame rate = 150; expected 30', 'Frame height = 160; expected 1024', 'Frame width = 160; expected 1280'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)
        # Test frame data warnings
        gpio = [None, None, None, {k: v[:1] for k, v in self.gpio[-1].items()}]
        load_embedded_frame_data.return_value = (self.count[-100:], gpio)
        with self.assertLogs(video.__name__, 30) as log:
            self.assertFalse(video.validate_video(self.video_path, self.config))
            expected = {'1 event(s) on GPIO #4', 'Frame count / video frame mismatch - frame counts = 100; video frames = 1000'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)
        # Test frame data errors
        load_embedded_frame_data.return_value = (self.count + 100, [None] * 4)
        with self.assertLogs(video.__name__, 40) as log:
            self.assertFalse(video.validate_video(self.video_path, self.config))
            expected = {'Missed frames (9.09%) - frame data N = 1100; video file N = 1000', 'No GPIO events detected.'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)

    def test_validate_video_missing(self):
        """Test iblrig.video.validate_video function when video missing."""
        # Test with non-existent file
        with self.assertLogs(video.__name__, 50) as log:
            video_path = self.video_path.with_name('_iblrig_rightCamera.raw.avi')
            self.assertFalse(video.validate_video(video_path, self.config))
            self.assertTrue(log.records[-1].getMessage().startswith('Raw video file does not exist'))
        # Test with empty file
        with tempfile.NamedTemporaryFile(suffix=self.video_path.name) as video_path, self.assertLogs(video.__name__, 50) as log:
            self.assertFalse(video.validate_video(Path(video_path.name), self.config))
            self.assertTrue(log.records[-1].getMessage().startswith('Raw video file empty'))
        # Test with non-empty, unreadable video file
        with self.assertLogs(video.__name__, 50) as log:
            self.assertFalse(video.validate_video(self.video_path, self.config))
            self.assertTrue(log.records[-1].getMessage().startswith('Failed to open video file'))


if __name__ == '__main__':
    unittest.main()
