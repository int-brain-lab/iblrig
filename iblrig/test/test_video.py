import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call, ANY
import tempfile
import sys

import yaml
from iblutil.util import Bunch
import numpy as np
"""In order to mock iblrig.video_pyspin.enable_camera_trigger we must mock PySpin here."""
sys.modules['PySpin'] = MagicMock()

from iblrig import video  # noqa
from iblrig.path_helper import load_pydantic_yaml  # noqa
from iblrig.pydantic_definitions import HardwareSettings  # noqa


class TestDownloadFunction(unittest.TestCase):
    @patch('one.webclient.AlyxClient.download_file', return_value=('mocked_tmp_file', 'mocked_md5_checksum'))
    @patch('os.rename', return_value=None)
    def test_download_from_alyx_or_flir(self, mock_os_rename, mock_alyx_download):
        asset = 123
        filename = 'test_file.txt'

        # Call the function
        result = video._download_from_alyx_or_flir(asset, filename, 'mocked_md5_checksum')

        # Assertions
        expected_out_file = Path.home().joinpath('Downloads', filename)
        self.assertEqual(result, expected_out_file)
        mock_alyx_download.assert_called_once_with(
            f'resources/spinnaker/{filename}', target_dir=Path(expected_out_file.parent), clobber=True, return_md5=True
        )
        mock_os_rename.assert_called_once_with('mocked_tmp_file', expected_out_file)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.old_params = Bunch({
            'DATA_FOLDER_PATH': r'D:\iblrig_data\Subjects',
            'REMOTE_DATA_FOLDER_PATH': r'\\iblserver.champalimaud.pt\ibldata\Subjects',
            'BODY_CAM_IDX': 0,
            'LEFT_CAM_IDX': 3,
            'RIGHT_CAM_IDX': 2,
        })
        params_dict_mock = patch('iblrig.video.load_params_dict', return_value=self.old_params)
        params_dict_mock.start()
        self.addCleanup(params_dict_mock.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._settings = {}
        for file in ('iblrig', 'hardware'):
            filepath = Path(video.__file__).parents[1].joinpath('settings', f'{file}_settings.yaml')
            if filepath.exists():
                with open(filepath, 'r') as fp:
                    self._settings[filepath] = fp.read()

    @patch('iblrig.video.params.getfile')
    def test_patch_old_params(self, getfile_mock):
        (old_file := Path(self.tmp.name, '.videopc_params')).touch()
        getfile_mock.return_value = old_file
        video.patch_old_params(remove_old=False)
        patched = self._load_patched_settings()  # Load the patched settings
        self.assertIn('device_cameras', patched['hardware_settings'])
        for cam, idx in dict(left=3, right=2, body=0).items():
            self.assertEqual(idx, patched['hardware_settings']['device_cameras'][cam]['INDEX'])
        self.assertEqual(r'D:\iblrig_data', patched['iblrig_settings']['iblrig_local_data_path'])
        self.assertEqual(r'\\iblserver.champalimaud.pt\ibldata', patched['iblrig_settings']['iblrig_remote_data_path'])
        self.assertTrue(old_file.exists(), 'failed to keep old settings file')

        # Check this works without settings files
        for filepath in self._settings:
            filepath.unlink()
        # Test insertion of 'subjects' path key if old location doesn't end in 'Subjects'
        for key in ('DATA_FOLDER_PATH', 'REMOTE_DATA_FOLDER_PATH'):
            self.old_params[key] = self.old_params[key].replace('Subjects', 'foobar')
        video.patch_old_params(remove_old=True)
        patched = self._load_patched_settings()  # Load the patched settings
        self.assertEqual(self.old_params['DATA_FOLDER_PATH'], patched['iblrig_settings']['iblrig_local_subjects_path'])
        self.assertEqual(self.old_params['REMOTE_DATA_FOLDER_PATH'], patched['iblrig_settings']['iblrig_remote_subjects_path'])
        self.assertFalse(old_file.exists(), 'failed to remove old settings file')

        video.patch_old_params()  # Shouldn't raise after removing old settings

    def _load_patched_settings(self):
        patched = {}
        for settings_file in self._settings:
            with open(settings_file, 'r') as fp:
                patched[settings_file.stem] = yaml.safe_load(fp)
        return patched

    def tearDown(self):
        for filepath, data in getattr(self, '_settings', {}).items():
            with open(filepath, 'w') as fp:
                fp.write(data)


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
            'leftCameraIndex': 1, 'rightCameraIndex': 1,
            'FileNameLeft': str(raw_data_folder / '_iblrig_leftCamera.raw.avi'),
            'FileNameLeftData': str(raw_data_folder / '_iblrig_leftCamera.frameData.bin'),
            'FileNameRight': str(raw_data_folder / '_iblrig_rightCamera.raw.avi'),
            'FileNameRightData': str(raw_data_folder / '_iblrig_rightCamera.frameData.bin')
        }
        expected = [call(workflows.setup, ANY), call(workflows.recording, expected_pars, wait=False)]
        call_bonsai.assert_has_calls(expected)

        # Test config validation
        self.assertRaises(ValueError, video.prepare_video_session, self.subject, 'training')
        session().hardware_settings = hws.construct()
        self.assertRaises(ValueError, video.prepare_video_session, self.subject, 'training')


class TestValidateVideo(unittest.TestCase):
    """Test for iblrig.video.validate_video."""
    def setUp(self):
        hws = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')
        self.config = hws['device_cameras']['default']['left']
        self.meta = Bunch(length=1000, fps=30, height=1024, width=1280, duration=1000 * 30)
        self.count = np.arange(self.meta['length'])
        n = 300  # The number of GPIO events
        pin = {'indices': np.round(np.linspace(0, self.count.size, n)), 'polarities': np.ones(n)}
        self.gpio = [None, None, None, pin]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.video_path = Path(tmp.name).joinpath(
            'subject', '2020-01-01', '001', 'raw_video_data', '_iblrig_leftCamera.raw.avi')
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
            expected = {'300 event(s) on GPIO #4', 'Duration = 30000.00', 'N frames = 1000'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)
        # Test video meta warnings
        config = self.config.copy()
        config.HEIGHT = config.WIDTH = 160
        config.FPS = 150
        with self.assertLogs(video.__name__, 30) as log:
            self.assertFalse(video.validate_video(self.video_path, config))
            expected = {'Frame rate = 150; expected 30',
                        'Frame height = 160; expected 1024',
                        'Frame width = 160; expected 1280'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)
        # Test frame data warnings
        gpio = [None, None, None, {k: v[:1] for k, v in self.gpio[-1].items()}]
        load_embedded_frame_data.return_value = (self.count[-100:], gpio)
        with self.assertLogs(video.__name__, 30) as log:
            self.assertFalse(video.validate_video(self.video_path, self.config))
            expected = {'1 event(s) on GPIO #4',
                        'Missed frames - frame data N = 999; video file N = 1000'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)
        # Test frame data errors
        load_embedded_frame_data.return_value = (self.count[:100], [None] * 4)
        with self.assertLogs(video.__name__, 40) as log:
            self.assertFalse(video.validate_video(self.video_path, self.config))
            expected = {'Frame count / video frame mismatch - frame counts = 99; video frames = 1000',
                        'No GPIO events detected.'}
            self.assertCountEqual(set(x.getMessage() for x in log.records), expected)

    def test_validate_video_missing(self):
        """Test iblrig.video.validate_video function when video missing."""
        # Test with non-existent file
        with self.assertLogs(video.__name__, 50) as log:
            video_path = self.video_path.with_name('_iblrig_rightCamera.raw.avi')
            self.assertFalse(video.validate_video(video_path, self.config))
            self.assertTrue(log.records[-1].getMessage().startswith('Raw video file does not exist'))
        # Test with empty file
        with tempfile.NamedTemporaryFile(suffix=self.video_path.name) as video_path:
            with self.assertLogs(video.__name__, 50) as log:
                self.assertFalse(video.validate_video(Path(video_path.name), self.config))
                self.assertTrue(log.records[-1].getMessage().startswith('Raw video file empty'))
        # Test with non-empty, unreadable video file
        with self.assertLogs(video.__name__, 50) as log:
            self.assertFalse(video.validate_video(self.video_path, self.config))
            self.assertTrue(log.records[-1].getMessage().startswith('Failed to open video file'))


if __name__ == '__main__':
    unittest.main()
