import unittest
from subprocess import CalledProcessError
from unittest.mock import patch
from packaging import version

from iblrig.version_management import is_dirty, check_for_updates


class TestCheckForUpdates(unittest.TestCase):

    @patch('iblrig.version_management.get_local_version')
    @patch('iblrig.version_management.get_remote_version')
    @patch('iblrig.tools.internet_available')
    def test_update_available(self, mock_internet, mock_get_remote_version, mock_get_local_version):
        mock_internet.return_value = True
        mock_get_remote_version.return_value = version.parse('2.0.0')
        mock_get_local_version.return_value = version.parse('1.0.0')
        update_available, latest_version = check_for_updates()
        self.assertTrue(update_available)
        self.assertEqual(latest_version, '2.0.0')

    @patch('iblrig.version_management.get_local_version')
    @patch('iblrig.version_management.get_remote_version')
    @patch('iblrig.tools.internet_available')
    def test_no_update_available(self, mock_internet, mock_get_remote_version, mock_get_local_version):
        mock_internet.return_value = True
        mock_get_remote_version.return_value = version.parse('1.0.0')
        mock_get_local_version.return_value = version.parse('1.0.0')
        update_available, latest_version = check_for_updates()
        self.assertFalse(update_available)
        self.assertEqual(latest_version, '1.0.0')



class TestIsDirty(unittest.TestCase):

    @patch('iblrig.version_management.check_call')
    def test_dirty_directory(self, mock_check_call):
        mock_check_call.return_value = 1  # Simulating a non-zero return value for a dirty directory
        self.assertTrue(is_dirty())

    @patch('iblrig.version_management.check_call')
    def test_clean_directory(self, mock_check_call):
        mock_check_call.return_value = 0  # Simulating a return value of zero for a clean directory
        self.assertFalse(is_dirty())

    @patch('iblrig.version_management.check_call')
    def test_exception_handling(self, mock_check_call):
        mock_check_call.side_effect = CalledProcessError(1, "cmd")
        self.assertTrue(is_dirty())
