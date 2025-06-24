import asyncio
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from unittest.mock import ANY, DEFAULT, MagicMock, call, patch

import numpy as np

from iblutil.io import net
from iblutil.util import Bunch

"""In order to mock iblrig.video_pyspin.enable_camera_trigger we must mock PySpin here."""
sys.modules['PySpin'] = MagicMock()

from iblrig import video  # noqa
from iblrig.test.base import BaseTestCases  # noqa
from iblrig.path_helper import load_pydantic_yaml  # noqa
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


@patch('iblrig.video.HAS_PYSPIN', True)
@patch('iblrig.video.HAS_SPINNAKER', True)
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
        # Check log file initiated and moved to session folder
        log_file = raw_data_folder.joinpath('_ibl_log.info-acquisition.log')
        self.assertTrue(log_file.exists() and log_file.stat().st_size > 0)
        # When file logging fails, there should be a warning
        with (
            patch('iblrig.video.setup_logger', side_effect=(DEFAULT, OSError)),
            self.assertWarns(UserWarning, msg='Failed to set up logs'),
        ):
            session = video.CameraSession(**self.task_kwargs)
        session = video.CameraSession(**self.task_kwargs)
        with patch.object(session, '_copy_log_to_session', side_effect=OSError), self.assertLogs('iblrig', level='ERROR'):
            session.run()
        # Check the original log file still exists
        self.assertTrue(any(Path(tempfile.gettempdir()).glob('iblrig_logs/????????-??????_camera-session.log')))

        # Test validation
        self.assertRaises(NotImplementedError, video.CameraSession, append=True)
        # Pass in config name not defined in hardware camera settings
        self.assertRaises(ValueError, video.CameraSession, config_name='training', **self.task_kwargs)


class TestCameraSessionNetworked(unittest.IsolatedAsyncioTestCase, BaseCameraTest):
    """Tests for the iblrig.video.CameraSessionNetworked class."""

    def setUp(self):
        super().setUp()
        del self.task_kwargs['subject']  # not used in these tests
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
        self.session = video.CameraSessionNetworked(**self.task_kwargs)
        # These two lines replace a call to `session.listen`
        self.session.communicator = self.communicator
        self.session._status = net.base.ExpStatus.CONNECTED

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

    @patch('iblrig.video.call_bonsai')
    @patch('iblrig.video_pyspin.enable_camera_trigger')
    async def test_run_video_session(self, enable_camera_trigger, call_bonsai):
        """Test iblrig.video.CameraSessionNetworked.run method."""
        # Some test hardware settings
        config = self.task_kwargs['hardware_settings']['device_cameras']['default']
        workflows = config['BONSAI_WORKFLOW']
        self.assertEqual(self.session.config, config)

        def _end_bonsai_proc():
            """Return args with added side effect of signalling Bonsai subprocess termination."""
            addr = '192.168.0.5:99998'
            info_msg = ((net.base.ExpStatus.CONNECTED, {'subject_name': 'foo'}), addr, net.base.ExpMessage.EXPINFO)
            init_msg = ([{'exp_ref': f'{date.today()}_1_foo'}], addr, net.base.ExpMessage.EXPINIT)
            start_msg = ((f'{date.today()}_1_foo', {}), addr, net.base.ExpMessage.EXPSTART)
            status_msg = (net.base.ExpStatus.RUNNING, addr, net.base.ExpMessage.EXPSTATUS)
            for call_number, msg in enumerate((info_msg, init_msg, start_msg, status_msg, status_msg)):
                match call_number:  # before yielding each message, make some assertions on the current state of the session
                    # Before any messages processed
                    case 0:
                        self.assertIs(self.session.status, net.base.ExpStatus.CONNECTED)
                        self.assertIsNone(self.session.exp_ref)
                    # After info message processed
                    case 1:
                        self.assertIs(self.session.status, net.base.ExpStatus.CONNECTED)
                    # After init message processed
                    case 2:
                        self.assertIs(self.session.status, net.base.ExpStatus.INITIALIZED)
                        self.assertEqual(f'{date.today()}_1_foo', self.session.exp_ref)
                        bonsai_task = next((t for t in self.session._async_tasks if t.get_name() == 'bonsai'), None)
                        self.assertIsNotNone(bonsai_task, 'failed to add named bonsai wait task to task set')
                        self.assertFalse(bonsai_task.done(), 'bonsai task unexpectedly cancelled')
                        self.call_bonsai_async.return_value.wait.assert_awaited_once()
                    # After start message processed
                    case 3:
                        self.assertIs(self.session.status, net.base.ExpStatus.RUNNING)
                        # Simulate user ending bonsai subprocess
                        self.bonsai_subprocess_future.set_result(0)
                        # End loop by simulating communicator object disconnecting
                        self.communicator.is_connected = False
                    # case _:
                    #     self.assertIs(self.session.status, net.base.ExpStatus.STOPPED)
                yield msg

        responses = _end_bonsai_proc()
        self.communicator.on_event.side_effect = lambda evt: next(responses)
        await self.session.run()
        self.communicator.close.assert_called_once()
        self.communicator.on_event.assert_awaited_with(net.base.ExpMessage.any())
        self.assertEqual(net.base.ExpStatus.STOPPED, self.session.status)

        # Validate calls
        expected = [call(enable=False), call(enable=True), call(enable=False)]
        enable_camera_trigger.assert_has_calls(expected)
        raw_data_folder = self.session.paths['SESSION_RAW_DATA_FOLDER']
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
        # Check log file initiated and moved to session folder
        log_file = raw_data_folder.joinpath('_ibl_log.info-acquisition.log')
        self.assertTrue(log_file.exists() and log_file.stat().st_size > 0)

    @patch('iblrig.video.call_bonsai')
    @patch('iblrig.video_pyspin.enable_camera_trigger')
    async def test_log_move_error(self, *_):
        """Check handles log move error without raising."""
        handlers = self.session.logger.handlers
        handler = next(h for h in handlers if getattr(h, 'baseFilename', '').endswith('_camera-session.log'))
        temp_log_file = Path(handler.baseFilename)
        self.assertTrue(temp_log_file.exists() and temp_log_file.is_relative_to(tempfile.gettempdir()))

        def _end_bonsai_proc():
            """Return args with added side effect of signalling Bonsai subprocess termination."""
            addr = '192.168.0.5:99998'
            info_msg = ((net.base.ExpStatus.CONNECTED, {'subject_name': 'foo'}), addr, net.base.ExpMessage.EXPINFO)
            init_msg = ([{'exp_ref': f'{date.today()}_1_foo'}], addr, net.base.ExpMessage.EXPINIT)
            start_msg = ((f'{date.today()}_1_foo', {}), addr, net.base.ExpMessage.EXPSTART)
            status_msg = (net.base.ExpStatus.RUNNING, addr, net.base.ExpMessage.EXPSTATUS)
            for msg in (info_msg, init_msg, start_msg, status_msg):  # noqa: UP028
                yield msg
            # End loop by simulating communicator object disconnecting
            self.communicator.is_connected = False
            yield status_msg

        responses = _end_bonsai_proc()
        self.communicator.on_event.side_effect = lambda evt: next(responses)

        with patch.object(self.session, '_copy_log_to_session', side_effect=OSError), self.assertLogs('iblrig', level='ERROR'):
            await self.session.run()
        # Check the original log file still exists
        self.assertTrue(temp_log_file.exists() and temp_log_file.stat().st_size > 0)

    @patch('iblrig.video.call_bonsai')
    @patch('iblrig.video_pyspin.enable_camera_trigger')
    async def test_error_handling(self, *_):
        """Check handles message errors when running."""

        def _message_mock_1():
            """Mock two init messages in a row, both with different expRefs."""
            addr = '192.168.0.5:99998'
            for ref in ('2020-01-01_1_foo', '2020-01-01_1_bar'):
                yield [{'exp_ref': ref}], addr, net.base.ExpMessage.EXPINIT

        responses_1 = _message_mock_1()
        self.communicator.on_event.side_effect = lambda evt: next(responses_1)

        with self.assertRaises(AssertionError) as cm:
            await self.session.run()
            self.assertEqual(str(cm.exception), 'expected 2025-03-12_1_foo, got 2025-03-12_1_bar')
        # Check the communicator was closed
        self.communicator.close.assert_called_once()
        self.assertFalse(any(self.session._async_tasks))

        # When the session is running, the communicator should remain open
        await self.asyncSetUp()  # reset the session

        def _message_mock_2():
            """Mock two init messages in a row, both with different expRefs."""
            addr = '192.168.0.5:99998'
            yield (f'{date.today()}_1_foo', {}), addr, net.base.ExpMessage.EXPSTART
            while True:  # sometimes the on_event method is awaited again before the bonsai task
                yield [{'exp_ref': '2020-01-01_1_bar'}], addr, net.base.ExpMessage.EXPINIT
                if not self.bonsai_subprocess_future.done():
                    self.bonsai_subprocess_future.set_result(0)
                    self.communicator.is_connected = False

        responses_2 = _message_mock_2()
        self.communicator.on_event.side_effect = lambda evt: next(responses_2)
        # Should catch and log error instead of raising
        with self.assertLogs(self.session.logger.name, 'ERROR') as cm:
            await self.session.run()
            record = next((r.getMessage() for r in cm.records if r.levelno == 40), '')
            self.assertRegex(record, r'2020-01-01_1_bar received; already running [\d\-_]+foo')

    async def test_process_keyboard_input(self):
        """Test iblrig.video.CameraSessionNetworked._process_keyboard_input method."""
        # With blank input should simply return
        with self.assertNoLogs(self.session.logger, 'INFO'):
            await self.session._process_keyboard_input('')
        self.communicator.close.assert_not_called()
        # With unknown input should log error
        with self.assertLogs(self.session.logger, 'ERROR'):
            await self.session._process_keyboard_input('FOO')
            self.communicator.close.assert_not_called()
        # With STOP should log info and stop recording
        with self.assertLogs(self.session.logger, 'INFO'), patch.object(self.session, 'stop_recording') as stop:
            await self.session._process_keyboard_input('STOP')
            stop.assert_awaited_once()
            self.communicator.close.assert_not_called()
        # With START should log info and start recording
        assert self.session.exp_ref is None
        with self.assertLogs(self.session.logger, 'ERROR'), patch.object(self.session, 'on_start') as start:
            await self.session._process_keyboard_input('START')
            start.assert_not_awaited()
        self.session.session_info = dict(SUBJECT_NAME='foo', SESSION_START_TIME=datetime.now().isoformat(), SESSION_NUMBER=1)
        assert self.session.exp_ref
        with self.assertLogs(self.session.logger, 'INFO'), patch.object(self.session, 'on_start') as start:
            await self.session._process_keyboard_input('START')
            exp_ref = f'{date.today()}_1_foo'
            start.assert_awaited_once_with([exp_ref, {}], None)
        # With QUIT should log info and close communicator
        with self.assertLogs(self.session.logger, 'INFO'), patch.object(self.session, 'stop_recording') as stop:
            await self.session._process_keyboard_input('QUIT')
            stop.assert_not_awaited()
            self.communicator.close.assert_called()
            self.session.bonsai_process = MagicMock()
            self.session.bonsai_process.returncode = 0
            await self.session._process_keyboard_input('QUIT')
            stop.assert_not_awaited()
            self.session.bonsai_process.returncode = None
            await self.session._process_keyboard_input('QUIT')
            stop.assert_awaited_once()
        # With QUIT! should call close method
        self.communicator.close.reset_mock()
        with self.assertLogs(self.session.logger, 'INFO'), patch.object(self.session, 'close', wraps=self.session.close) as close:
            await self.session._process_keyboard_input('QUIT!!!')
            close.assert_called_once()
            self.communicator.close.assert_called_once()
            self.assertFalse(any(self.session._async_tasks))


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
