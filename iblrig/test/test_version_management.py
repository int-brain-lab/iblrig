import unittest
from pathlib import Path
from subprocess import CalledProcessError
from unittest.mock import patch

from packaging import version

from iblrig.constants import BASE_DIR
from iblrig.version_management import check_for_updates, get_detailed_version_string, get_local_version, is_dirty


class TestCheckForUpdates(unittest.TestCase):
    @patch('iblrig.version_management.get_local_version', return_value=version.parse('1.0.0'))
    @patch('iblrig.version_management.get_remote_version', return_value=version.parse('2.0.0'))
    @patch('iblrig.tools.internet_available', return_value=True)
    def test_update_available(self, *_):
        update_available, latest_version = check_for_updates()
        self.assertTrue(update_available)
        self.assertEqual(latest_version, '2.0.0')

    @patch('iblrig.version_management.get_local_version', return_value=version.parse('1.0.0'))
    @patch('iblrig.version_management.get_remote_version', return_value=version.parse('1.0.0'))
    @patch('iblrig.tools.internet_available', return_value=True)
    def test_no_update_available(self, *_):
        update_available, latest_version = check_for_updates()
        self.assertFalse(update_available)
        self.assertEqual(latest_version, '1.0.0')


class TestGetLocalVersion(unittest.TestCase):
    def test_get_local_version_success(self):
        with self.assertNoLogs('iblrig', level='ERROR'):
            result = get_local_version()
            self.assertIsNotNone(result)
            self.assertIsInstance(result, version.Version)

    @patch('iblrig.version_management.__version__', 'invalid')
    def test_get_local_version_failure(self):
        with self.assertLogs('iblrig', level='ERROR'):
            result = get_local_version()
            self.assertIsNone(result)


class TestGetDetailedVersionString(unittest.TestCase):
    @patch('iblrig.version_management.internet_available', return_value=True)
    @patch('iblrig.version_management.get_remote_tags')
    @patch('iblrig.version_management.check_output', return_value='1.0.0-42-gfe39a9d2-dirty\n')
    def test_detailed_version_string_generation(self, mock_check_output, mock_get_remote_tags, mock_internet_available):
        with self.assertNoLogs('iblrig', level='ERROR'):
            result = get_detailed_version_string('1.0.0')
            self.assertEqual(result, '1.0.0.post42+dirty')
            mock_internet_available.assert_called_once()
            mock_get_remote_tags.assert_called_once()
            mock_check_output.assert_called_once()

    @patch('iblrig.version_management.internet_available', return_value=False)
    def test_detailed_version_string_no_internet(self, mock_internet_available):
        with self.assertNoLogs('iblrig', level='ERROR'):
            result = get_detailed_version_string('1.0.0')
            self.assertEqual(result, '1.0.0')
            mock_internet_available.assert_called_once()

    @patch('iblrig.version_management.IS_GIT', False)
    def test_detailed_version_string_no_git(self):
        with self.assertLogs('iblrig', level='ERROR'):
            result = get_detailed_version_string('1.0.0')
            self.assertEqual(result, '1.0.0')


class TestIsDirty(unittest.TestCase):
    @patch('iblrig.version_management.check_call')
    def test_dirty_directory(self, mock_check_call):
        mock_check_call.return_value = 1
        self.assertTrue(is_dirty())

    @patch('iblrig.version_management.check_call')
    def test_clean_directory(self, mock_check_call):
        mock_check_call.return_value = 0
        self.assertFalse(is_dirty())

    @patch('iblrig.version_management.check_call')
    def test_exception_handling(self, mock_check_call):
        mock_check_call.side_effect = CalledProcessError(1, 'cmd')
        self.assertTrue(is_dirty())


class TestChangeLog(unittest.TestCase):
    def test_change_log(self):
        with Path(BASE_DIR).joinpath('CHANGELOG.md').open() as f:
            assert str(get_local_version()) in f.read()
