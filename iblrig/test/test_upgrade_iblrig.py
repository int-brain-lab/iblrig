import unittest
from subprocess import CalledProcessError
from unittest.mock import patch

from packaging.version import Version

import iblrig.upgrade_iblrig
from iblrig.upgrade_iblrig import _exit_or_raise, call_subprocesses, upgrade


class TestExitOrRaise(unittest.TestCase):
    @patch('sys.exit')
    @patch('iblrig.upgrade_iblrig.log.error')
    def test_raise_exception_true(self, mock_log_error, mock_sys_exit):
        error_message = 'Something went wrong!'
        exception_instance = Exception(error_message)
        with self.assertRaises(Exception) as context:
            _exit_or_raise(exception_instance)
        self.assertEqual(context.exception, exception_instance)
        self.assertEqual(str(context.exception), error_message)
        mock_log_error.assert_not_called()
        mock_sys_exit.assert_not_called()

    @patch('sys.exit')
    @patch('iblrig.upgrade_iblrig.log.error')
    def test_exit_with_return_code(self, mock_log_error, mock_sys_exit):
        error_message = 'Something went wrong!'
        return_code = 99
        _exit_or_raise(error_message, raise_exception=False, return_code=return_code)
        mock_log_error.assert_called_once_with(error_message)
        mock_sys_exit.assert_called_once_with(return_code)

    @patch('sys.exit')
    @patch('iblrig.upgrade_iblrig.log.error')
    def test_exit_without_return_code(self, mock_log_error, mock_sys_exit):
        error_message = CalledProcessError(cmd='OMG!', returncode=42)
        _exit_or_raise(error_message, raise_exception=False)
        mock_log_error.assert_called_once_with(str(error_message))
        mock_sys_exit.assert_called_once_with(error_message.returncode)


class TestCallSubprocesses(unittest.TestCase):
    @patch('iblrig.upgrade_iblrig.run')
    @patch('iblrig.upgrade_iblrig.log')
    @patch('sys.executable', 'python')
    @patch('iblrig.upgrade_iblrig.BASE_DIR', '/base/dir')
    def test_call_subprocesses_without_reset(self, mock_log, mock_run):
        call_subprocesses(reset_repo=False)
        reset_call = ['git', 'reset', '--hard']
        calls = [
            ['git', 'pull', '--tags'],
            ['python', '-m', 'pip', 'install', '-U', 'pip'],
            ['python', '-m', 'pip', 'install', '-U', '-e', iblrig.upgrade_iblrig.BASE_DIR],
        ]
        kwargs = {'cwd': iblrig.upgrade_iblrig.BASE_DIR, 'check': True}
        for call in calls:
            mock_log.warning.assert_any_call('\n' + ' '.join(call))
            mock_run.assert_any_call(call, **kwargs)
        self.assertTrue(reset_call not in [f.args for f in mock_run.mock_calls])

    @patch('iblrig.upgrade_iblrig.run')
    @patch('iblrig.upgrade_iblrig.log')
    @patch('sys.executable', 'python')
    @patch('iblrig.upgrade_iblrig.BASE_DIR', '/base/dir')
    def test_call_subprocesses_with_reset(self, mock_log, mock_run):
        call_subprocesses(reset_repo=True)
        calls = [
            ['git', 'reset', '--hard'],
            ['git', 'pull', '--tags'],
            ['python', '-m', 'pip', 'install', '-U', 'pip'],
            ['python', '-m', 'pip', 'install', '-U', '-e', iblrig.upgrade_iblrig.BASE_DIR],
        ]
        kwargs = {'cwd': iblrig.upgrade_iblrig.BASE_DIR, 'check': True}
        for call in calls:
            mock_log.warning.assert_any_call('\n' + ' '.join(call))
            mock_run.assert_any_call(call, **kwargs)


class TestUpgradeFunction(unittest.TestCase):
    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_local_version', return_value=None)
    @patch('iblrig.upgrade_iblrig.call_subprocesses')
    def test_upgrade_no_local_version(self, mock_call_subprocesses, mock_get_local_version, mock_check_upgrade_prerequisites):
        with self.assertRaises(Exception):
            upgrade(raise_exceptions=True)
        mock_check_upgrade_prerequisites.assert_called_once()
        mock_get_local_version.assert_called_once()
        mock_call_subprocesses.assert_not_called()

    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_remote_version', return_value=None)
    @patch('iblrig.upgrade_iblrig.call_subprocesses')
    def test_upgrade_no_remote_version(self, mock_call_subprocesses, mock_get_remote_version, mock_check_upgrade_prerequisites):
        with self.assertRaises(Exception):
            upgrade(raise_exceptions=True)
        mock_check_upgrade_prerequisites.assert_called_once()
        mock_get_remote_version.assert_called_once()
        mock_call_subprocesses.assert_not_called()

    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_local_version', return_value=Version('1.0.0'))
    @patch('iblrig.upgrade_iblrig.get_remote_version', return_value=Version('1.0.0'))
    @patch('iblrig.upgrade_iblrig.ask_user', return_value=False)
    @patch('iblrig.upgrade_iblrig.call_subprocesses')
    def test_upgrade_not_necessary(
        self,
        mock_call_subprocesses,
        mock_ask_user,
        mock_get_remote_version,
        mock_get_local_version,
        mock_check_upgrade_prerequisites,
    ):
        with self.assertRaises(SystemExit):
            upgrade(raise_exceptions=True)
        mock_check_upgrade_prerequisites.assert_called_once()
        mock_get_local_version.assert_called_once()
        mock_get_remote_version.assert_called_once()
        mock_ask_user.assert_called_once()
        mock_call_subprocesses.assert_not_called()

    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_local_version', return_value=Version('1.0.0'))
    @patch('iblrig.upgrade_iblrig.get_remote_version', return_value=Version('2.0.0'))
    @patch('iblrig.upgrade_iblrig.is_dirty', return_value=True)
    @patch('iblrig.upgrade_iblrig.ask_user', return_value=False)
    @patch('iblrig.upgrade_iblrig.call_subprocesses')
    def test_upgrade_dirty(
        self,
        mock_call_subprocesses,
        mock_ask_user,
        mock_is_dirty,
        mock_get_remote_version,
        mock_get_local_version,
        mock_check_upgrade_prerequisites,
    ):
        with self.assertRaises(SystemExit):
            upgrade(raise_exceptions=True)
        mock_check_upgrade_prerequisites.assert_called_once()
        mock_get_local_version.assert_called_once()
        mock_get_remote_version.assert_called_once()
        mock_ask_user.assert_called_once()
        mock_is_dirty.assert_called_once()
        mock_call_subprocesses.assert_not_called()

    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_local_version', return_value=Version('1.0.0'))
    @patch('iblrig.upgrade_iblrig.get_remote_version', return_value=Version('2.0.0'))
    @patch('iblrig.upgrade_iblrig.is_dirty', return_value=False)
    @patch('iblrig.upgrade_iblrig.ask_user')
    @patch('iblrig.upgrade_iblrig.call_subprocesses', side_effect=CalledProcessError(cmd='asd', returncode=42))
    def test_upgrade_subprocess_exception_raised(
        self,
        mock_call_subprocesses,
        mock_ask_user,
        mock_is_dirty,
        mock_get_remote_version,
        mock_get_local_version,
        mock_check_upgrade_prerequisites,
    ):
        with self.assertRaises(CalledProcessError):
            upgrade(raise_exceptions=True)
        mock_check_upgrade_prerequisites.assert_called_once()
        mock_get_local_version.assert_called_once()
        mock_get_remote_version.assert_called_once()
        mock_ask_user.assert_not_called()
        mock_is_dirty.assert_called_once()
        mock_call_subprocesses.assert_called_once()

    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_local_version', return_value=Version('1.0.0'))
    @patch('iblrig.upgrade_iblrig.get_remote_version', return_value=Version('2.0.0'))
    @patch('iblrig.upgrade_iblrig.is_dirty', return_value=False)
    @patch('iblrig.upgrade_iblrig.ask_user')
    @patch('iblrig.upgrade_iblrig.call_subprocesses', side_effect=CalledProcessError(cmd='asd', returncode=42))
    @patch('sys.exit')
    def test_upgrade_subprocess_exception_as_error(
        self,
        mock_exit,
        mock_call_subprocesses,
        mock_ask_user,
        mock_is_dirty,
        mock_get_remote_version,
        mock_get_local_version,
        mock_check_upgrade_prerequisites,
    ):
        with self.assertLogs(level='ERROR'):
            upgrade(raise_exceptions=False)
        mock_check_upgrade_prerequisites.assert_called_once()
        mock_get_local_version.assert_called_once()
        mock_get_remote_version.assert_called_once()
        mock_ask_user.assert_not_called()
        mock_is_dirty.assert_called_once()
        mock_call_subprocesses.assert_called_once()
        mock_exit.assert_called_once_with(42)

    @patch('iblrig.upgrade_iblrig.check_upgrade_prerequisites')
    @patch('iblrig.upgrade_iblrig.get_local_version', return_value=Version('1.0.0'))
    @patch('iblrig.upgrade_iblrig.get_remote_version', return_value=Version('2.0.0'))
    @patch('iblrig.upgrade_iblrig.is_dirty', return_value=False)
    @patch('iblrig.upgrade_iblrig.call_subprocesses')
    @patch('iblrig.upgrade_iblrig._exit_or_raise')
    @patch('sys.exit')
    def test_upgrade(
        self,
        mock_exit,
        mock_exit_or_raise,
        mock_call_subprocesses,
        mock_is_dirty,
        mock_get_remote_version,
        mock_get_local_version,
        mock_check_upgrade_prerequisites,
    ):
        upgrade(raise_exceptions=False, allow_reset=False)
        mock_check_upgrade_prerequisites.assert_called_once_with(exception_handler=mock_exit_or_raise, raise_exception=False)
        mock_get_local_version.assert_called_once()
        mock_get_remote_version.assert_called_once()
        mock_is_dirty.assert_called_once()
        mock_call_subprocesses.assert_called_once()
        mock_exit.assert_called_once_with(0)
