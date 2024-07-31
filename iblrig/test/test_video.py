import asyncio
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np
import yaml

from iblutil.io import net
from iblutil.util import Bunch

"""In order to mock iblrig.video_pyspin.enable_camera_trigger we must mock PySpin here."""
sys.modules['PySpin'] = MagicMock()

from iblrig import video  # noqa
from iblrig.test.base import BaseTestCases  # noqa
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


class BaseCameraTest(BaseTestCases.CommonTestTask):
    """A base class for camera hardware test fixtures."""

    def setUp(self):
        self.get_task_kwargs()
        self.tmp.joinpath('remote').mkdir()
        self.tmp.joinpath('local').mkdir()

    def get_task_kwargs(self, tmpdir=True):
        """Generate test task kwargs for typical video PC."""
        super().get_task_kwargs(tmpdir=tmpdir)
        # Some test hardware settings
        hws = self.task_kwargs['hardware_settings']
        hws['device_cameras'] = load_pydantic_yaml(HardwareSettings, 'hardware_settings_template.yaml')['device_cameras']
        hws['device_cameras']['default']['right'] = hws['device_cameras']['default']['left']
        hws['MAIN_SYNC'] = False
        # Some test rig settings
        settings = self.task_kwargs['iblrig_settings']
        settings['iblrig_remote_data_path'] = settings['iblrig_remote_subjects_path'] = self.tmp / 'remote'
        settings['iblrig_local_data_path'] = settings['iblrig_local_subjects_path'] = self.tmp / 'local'


class TestCameraSession(BaseCameraTest):
    """Test for iblrig.video.CameraSession class."""

    @patch('iblrig.video.HAS_PYSPIN', True)
    @patch('iblrig.video.HAS_SPINNAKER', True)
    @patch('builtins.input')
    @patch('iblrig.video.call_bonsai')
    @patch('iblrig.video_pyspin.enable_camera_trigger')
    def test_run_video_session(self, enable_camera_trigger, call_bonsai, _):
        """Test iblrig.video.CameraSession.run method."""
        (input_mock := patch('builtins.input')).start()
        self.addCleanup(input_mock.stop)

        config = self.task_kwargs['hardware_settings']['device_cameras']['default']
        workflows = config['BONSAI_WORKFLOW']

        session = video.CameraSession(**self.task_kwargs)
        self.assertEqual(session.config, config)
        session.run()

        # Validate calls
        expected = [call(enable=False), call(enable=True), call(enable=False)]
        enable_camera_trigger.assert_has_calls(expected)
        raw_data_folder = session.paths['SESSION_RAW_DATA_FOLDER']
        self.assertTrue(str(raw_data_folder).startswith(str(self.tmp)))
        expected_pars = {
            'LeftCameraIndex': 1,
            'RightCameraIndex': 1,
            'FileNameLeft': str(raw_data_folder / '_iblrig_leftCamera.raw.avi'),
            'FileNameLeftData': str(raw_data_folder / '_iblrig_leftCamera.frameData.bin'),
            'FileNameRight': str(raw_data_folder / '_iblrig_rightCamera.raw.avi'),
            'FileNameRightData': str(raw_data_folder / '_iblrig_rightCamera.frameData.bin'),
        }
        expected = [
            call(workflows.setup, ANY, debug=False, wait=True),
            call(workflows.recording, expected_pars, debug=False, wait=False),
        ]
        call_bonsai.assert_has_calls(expected)

        # Test validation
        self.assertRaises(NotImplementedError, video.CameraSession, append=True)
        # Pass in config name not defined in hardware camera settings
        self.assertRaises(ValueError, video.CameraSession, config_name='training', **self.task_kwargs)


class TestCameraSessionNetworked(unittest.IsolatedAsyncioTestCase, BaseCameraTest):
    """Tests for the iblrig.video.CameraSessionNetworked class."""

    def setUp(self):
        super().setUp()
        # Set up keyboad input mock - simply return empty string as await appears to be blocking
        self.keyboard = ''
        read_stdin = patch('iblrig.video.read_stdin')
        self.addCleanup(read_stdin.stop)
        read_stdin_mock = read_stdin.start()

        async def _stdin():
            yield self.keyboard

        read_stdin_mock.side_effect = _stdin

    async def asyncSetUp(self):
        self.communicator = mock.AsyncMock(spec=video.net.app.EchoProtocol)
        self.communicator.is_connected = True

        # Mock the call_bonsai_async function to return an async subprocess mock that awaits a
        # future that we can access via self.bonsai_subprocess_future
        self.bonsai_subprocess_future = asyncio.get_event_loop().create_future()
        self.addCleanup(self.bonsai_subprocess_future.cancel)

        async def _wait():
            return await self.bonsai_subprocess_future

        call_bonsai_async = patch('iblrig.video.call_bonsai_async')
        self.addCleanup(call_bonsai_async.stop)
        self.call_bonsai_async = call_bonsai_async.start()
        self.call_bonsai_async.return_value = mock.AsyncMock(spec=asyncio.subprocess.Process)
        self.call_bonsai_async.return_value.wait.side_effect = _wait

    @patch('iblrig.video.HAS_PYSPIN', True)
    @patch('iblrig.video.HAS_SPINNAKER', True)
    @patch('iblrig.video.call_bonsai')
    @patch('iblrig.video_pyspin.enable_camera_trigger')
    async def test_run_video_session(self, enable_camera_trigger, call_bonsai):
        """Test iblrig.video.CameraSessionNetworked.run method."""
        # Some test hardware settings
        task_kwargs = self.task_kwargs
        del task_kwargs['subject']
        config = task_kwargs['hardware_settings']['device_cameras']['default']
        workflows = config['BONSAI_WORKFLOW']

        session = video.CameraSessionNetworked(**task_kwargs)
        # These two lines replace a call to `session.listen`
        session.communicator = self.communicator
        session._status = net.base.ExpStatus.CONNECTED
        self.assertEqual(session.config, config)

        def _end_bonsai_proc():
            """Return args with added side effect of signalling Bonsai subprocess termination."""
            addr = '192.168.0.5:99998'
            info_msg = ((net.base.ExpStatus.CONNECTED, {'subject_name': 'foo'}), addr, net.base.ExpMessage.EXPINFO)
            init_msg = ({'exp_ref': f'{date.today()}_1_foo'}, addr, net.base.ExpMessage.EXPINIT)
            start_msg = ((f'{date.today()}_1_foo', {}), addr, net.base.ExpMessage.EXPSTART)
            status_msg = (net.base.ExpStatus.RUNNING, addr, net.base.ExpMessage.EXPSTATUS)
            for call_number, msg in enumerate((info_msg, init_msg, start_msg, status_msg, status_msg)):
                match call_number:  # before yielding each message, make some assertions on the current state of the session
                    # Before any messages processed
                    case 0:
                        self.assertIs(session.status, net.base.ExpStatus.CONNECTED)
                        self.assertIsNone(session.exp_ref)
                    # After info message processed
                    case 1:
                        self.assertIs(session.status, net.base.ExpStatus.CONNECTED)
                    # After init message processed
                    case 2:
                        self.assertIs(session.status, net.base.ExpStatus.INITIALIZED)
                        self.assertEqual(f'{date.today()}_1_foo', session.exp_ref)
                        bonsai_task = next((t for t in session._async_tasks if t.get_name() == 'bonsai'), None)
                        self.assertIsNotNone(bonsai_task, 'failed to add named bonsai wait task to task set')
                        self.assertFalse(bonsai_task.done(), 'bonsai task unexpectedly cancelled')
                        self.call_bonsai_async.return_value.wait.assert_awaited_once()
                    # After start message processed
                    case 3:
                        self.assertIs(session.status, net.base.ExpStatus.RUNNING)
                        # Simulate user ending bonsai subprocess
                        self.bonsai_subprocess_future.set_result(0)
                        # End loop by simulating communicator object disconnecting
                        self.communicator.is_connected = False
                    # case _:
                    #     self.assertIs(session.status, net.base.ExpStatus.STOPPED)
                yield msg

        reponses = _end_bonsai_proc()
        self.communicator.on_event.side_effect = lambda evt: next(reponses)
        await session.run()
        self.communicator.close.assert_called_once()
        self.communicator.on_event.assert_awaited_with(net.base.ExpMessage.any())
        self.assertEqual(net.base.ExpStatus.STOPPED, session.status)

        # Validate calls
        expected = [call(enable=False), call(enable=True), call(enable=False)]
        enable_camera_trigger.assert_has_calls(expected)
        raw_data_folder = session.paths['SESSION_RAW_DATA_FOLDER']
        self.assertTrue(str(raw_data_folder).startswith(str(self.tmp)))
        expected_pars = {
            'LeftCameraIndex': 1,
            'RightCameraIndex': 1,
            'FileNameLeft': str(raw_data_folder / '_iblrig_leftCamera.raw.avi'),
            'FileNameLeftData': str(raw_data_folder / '_iblrig_leftCamera.frameData.bin'),
            'FileNameRight': str(raw_data_folder / '_iblrig_rightCamera.raw.avi'),
            'FileNameRightData': str(raw_data_folder / '_iblrig_rightCamera.frameData.bin'),
        }
        call_bonsai.assert_called_once_with(
            workflows.setup, {'LeftCameraIndex': 1, 'RightCameraIndex': 1}, debug=False, wait=True
        )
        self.call_bonsai_async.assert_awaited_once_with(workflows.recording, expected_pars, debug=False)


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
