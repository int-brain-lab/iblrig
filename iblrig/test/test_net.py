"""Tests for iblrig.net module."""
import unittest
from unittest.mock import patch, Mock, ANY
from pathlib import Path
import tempfile

import yaml
from iblutil.io import net
from one.api import OneAlyx, One
import one.params

import iblrig.net


class TestRemoteDeviceFunctions(unittest.IsolatedAsyncioTestCase):
    """Tests for get_remote_devices_file, get_remote_devices, check_uri_match, etc."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmpdir = Path(tmp.name)

    @patch('iblrig.net.get_local_and_remote_paths')
    def test_get_remote_devices_file(self, paths_mock):
        """Test get_remote_devices_file function."""
        paths_mock.return_value = paths = {'remote_data_folder': None}
        # Check null remote server path
        self.assertIsNone(iblrig.net.get_remote_devices_file())
        # Check with remote server path
        paths['remote_data_folder'] = self.tmpdir
        file = iblrig.net.get_remote_devices_file()
        self.assertEqual(self.tmpdir / 'remote_devices.yaml', file)

    @patch('iblrig.net.get_remote_devices_file')
    def test_get_remote_devices(self, filename_mock):
        """Test get_remote_devices function."""
        # Check returns empty dict when remote devices file does not exist
        filename_mock.return_value = None
        self.assertEqual({}, iblrig.net.get_remote_devices())
        filename_mock.return_value = self.tmpdir / 'remote_devices.yaml'
        self.assertEqual({}, iblrig.net.get_remote_devices())

        remote_devices = {'cameras': 'udp://127.0.0.1:10000', 'neuropixel': 'udp://127.0.0.2'}
        with open(self.tmpdir / 'remote_devices.yaml', 'w') as f:
            yaml.safe_dump(remote_devices, f)
        self.assertEqual(remote_devices, iblrig.net.get_remote_devices())

    @patch('iblrig.net.get_remote_devices_file')
    async def test_check_uri_match(self, filename_mock):
        """Test check_uri_match function."""
        filename_mock.return_value = self.tmpdir / 'remote_devices.yaml'
        communicator_mock = Mock(spec_set=net.app.EchoProtocol)
        communicator_mock.name = 'foo'
        communicator_mock.server_uri = 'udp://127.0.0.1:11001'
        communicator_mock.port = 11001
        communicator_mock.hostname = '127.0.0.1'
        com, match = await iblrig.net.check_uri_match(communicator_mock)
        self.assertIs(com, communicator_mock)
        self.assertTrue(match)

        with open(self.tmpdir / 'remote_devices.yaml', 'r') as f:
            remote_devices = yaml.safe_load(f)
        self.assertEqual({'foo': 'udp://127.0.0.1:11001'}, remote_devices)

        # Now the device has been written to file, check behaviour when update=False
        with self.assertNoLogs(iblrig.net.__name__):
            _, match = await iblrig.net.check_uri_match(communicator_mock, update=False)
            self.assertTrue(match)

        # Should log a warning if communicator does not match
        communicator_mock.port = 9998
        with self.assertLogs(iblrig.net.__name__, 'WARNING'):
            _, match = await iblrig.net.check_uri_match(communicator_mock, update=False)
            self.assertFalse(match)

        # Check raises when file doesn't exist
        self.tmpdir.joinpath('remote_devices.yaml').unlink()
        with self.assertRaises(FileNotFoundError):
            await iblrig.net.check_uri_match(communicator_mock, update=True)

    @patch('iblutil.io.net.app.EchoProtocol.server')
    @patch('iblrig.net.check_uri_match')
    async def test_get_server_communicator(self, check_uri_mock, server_mock):
        """Test get_server_communicator function."""
        communicator_mock = Mock(spec_set=net.app.EchoProtocol)
        check_uri_mock.return_value = (communicator_mock, True)
        com, match = await iblrig.net.get_server_communicator(False, 'foo')
        self.assertIsNone(com)
        self.assertFalse(match)
        for value in ('', None, True):
            com, match = await iblrig.net.get_server_communicator(value, 'foo')
            self.assertIs(com, communicator_mock)
            check_uri_mock.assert_called_once()
            server_mock.assert_called_once_with(ANY, name='foo')
            uri, = server_mock.call_args.args
            self.assertTrue(uri.startswith('udp://') and uri.endswith(':11001'))
            server_mock.reset_mock(), check_uri_mock.reset_mock()
        _, match = await iblrig.net.get_server_communicator('tcp://192.168.0.88', 'foobar')
        self.assertTrue(match)
        server_mock.assert_called_once_with('tcp://192.168.0.88', name='foobar')


class TestTokenCallbacks(unittest.TestCase):
    """Tests for install_alyx_token and update_alyx_token functions."""

    def test_update_alyx_token(self):
        """Test update_alyx_token function."""
        one = OneAlyx(base_url='https://localhost:8000', silent=True, mode='local')
        one.alyx.logout()
        assert not one.alyx.is_logged_in
        token = ('https://test.alyx.internationalbrainlab.org',  {'j.doe': {'token': '123tok3n321'}})
        success = iblrig.net.update_alyx_token(token, ('localhost', 11001), one=one)
        self.assertTrue(success)
        self.assertTrue(one.alyx.is_logged_in)
        self.assertEqual('j.doe', one.alyx.user)
        self.assertEqual({'token': '123tok3n321'}, one.alyx._token)
        self.assertEqual({'token': '123tok3n321'}, one.alyx._par.TOKEN['j.doe'])
        self.assertEqual(token[0], one.alyx.base_url)

        one.alyx.logout()
        assert not one.alyx.is_logged_in
        success = iblrig.net.update_alyx_token(token, ('localhost', 11001))
        self.assertFalse(success)
        success = iblrig.net.update_alyx_token(token, ('localhost', 11001), one=One())
        self.assertFalse(success)
        success = iblrig.net.update_alyx_token(('https://test.alyx.internationalbrainlab.org', {}), ('localhost', 11001), one=one)
        self.assertFalse(success)

    @patch('iblutil.io.params.getfile')
    def test_install_alyx_token(self, getfile):
        """Test install_alyx_token function."""
        base_url = 'https://alyx.database.org'
        token = {'j.doe': {'token': '123tok3n321'}}

        with tempfile.TemporaryDirectory() as tmp:
            getfile.side_effect = Path(tmp).joinpath
            is_new_user = iblrig.net.install_alyx_token(base_url, token)
            self.assertTrue(is_new_user)
            par = one.params.get(base_url)
            self.assertEqual(token, par.TOKEN)
            token['j.doe']['token'] = 'abctok3ncba'
            self.assertFalse(iblrig.net.install_alyx_token(base_url, token))
            self.assertEqual(token, one.params.get(base_url).TOKEN)


if __name__ == '__main__':
    unittest.main()
