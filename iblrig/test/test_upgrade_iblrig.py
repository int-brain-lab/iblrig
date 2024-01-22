import unittest
from subprocess import CalledProcessError
from unittest.mock import patch

import iblrig.upgrade_iblrig
from iblrig.upgrade_iblrig import _exit_or_raise, call_subprocesses


class TestExitOrRaise(unittest.TestCase):
    @patch('iblrig.upgrade_iblrig.sys.exit')
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

    @patch('iblrig.upgrade_iblrig.sys.exit')
    @patch('iblrig.upgrade_iblrig.log.error')
    def test_exit_with_return_code(self, mock_log_error, mock_sys_exit):
        error_message = 'Something went wrong!'
        return_code = 99
        _exit_or_raise(error_message, raise_exception=False, return_code=return_code)
        mock_log_error.assert_called_once_with(error_message)
        mock_sys_exit.assert_called_once_with(return_code)

    @patch('iblrig.upgrade_iblrig.sys.exit')
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
