"""Tests for iblrig.net module."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import yaml

import iblrig.net
import one.params
from iblutil.io import net
from one.api import One, OneAlyx


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

        with open(self.tmpdir / 'remote_devices.yaml') as f:
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
            (uri,) = server_mock.call_args.args
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
        token = ('https://test.alyx.internationalbrainlab.org', {'j.doe': {'token': '123tok3n321'}})
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


class TestAuxiliaries(unittest.IsolatedAsyncioTestCase):
    """Test for net.Auxiliaries class."""

    @patch('iblrig.net.net.app.EchoProtocol.client')
    @patch('iblrig.net.net.app.Services', spec=net.app.Services)
    def setUp(self, services, com):
        self.services, self.com = services, com
        self.clients = {'rig_1': 'udp://192.168.0.1', 'rig_2': 'udp://192.168.0.2'}
        self.aux = iblrig.net.Auxiliaries(self.clients)
        self.addCleanup(self.aux.close)  # ensure threads joined
        assert getattr(self.aux, 'connected', False)
        with self.aux.connected:  # don't start testing until thread set up
            self.aux.connected.wait(timeout=0.5)

    def test_net(self):
        """Test creation of services."""
        self.services.assert_called()
        for name, uri in self.clients.items():
            self.com.assert_any_await(uri, name)

    @patch('iblrig.net.asyncio.sleep')
    def test_push(self, _):
        """Test Auxiliaries.push method.

        The async thread calls asyncio.sleep between message queue checks.
        Mocking this reduces overall execution time.
        """
        # Test without wait
        message = ['EXPINFO', {'subject': 'foobar'}]
        self.services().info.return_value = {'rig_1': ['EXPINFO'], 'rig_2': ['EXPINFO']}
        with self.aux.response_received:  # acquire lock
            r = self.aux.push(*message, wait=False)
            self.assertIsInstance(r, float)
            self.assertIn(r, self.aux._queued)
            self.aux.response_received.wait(1)
        self.assertIn(r, self.aux._log)
        self.services().info.assert_awaited()

        # Test with wait
        self.services().timeout = 1  # Need a timeout value
        message = ['EXPSTART', '2024-01-01_1_foo']
        response = {'rig_1': message, 'rig_2': message}
        self.services().start.return_value = response
        r = self.aux.push(*message, wait=True)
        self.assertEqual(response, r)
        self.assertFalse(self.aux._queued, 'failed to remove message from queue')
        self.assertIn(r, self.aux._log.values(), 'failed to add response to log')
        self.services().start.assert_awaited()

        # Test with errors
        # Bad message
        self.assertRaises(ValueError, self.aux.push, 'EXPBAR')
        self.services().init.side_effect = asyncio.TimeoutError('blah')
        with self.assertLogs(iblrig.net.__name__, 'ERROR'):
            r = self.aux.push('EXPINIT', wait=True)
        self.assertIsInstance(r, asyncio.TimeoutError)
        self.services().init.reset_mock(side_effect=True)
        # Push method won't allow compound messages so we add it directly in order to test NotImplemented response
        with self.aux.response_received:
            message = [net.base.ExpMessage.ALYX & net.base.ExpMessage.EXPEND, (), {}]
            self.aux._queued[1] = message
            self.aux.response_received.wait(timeout=0.5)
            self.assertIsInstance(self.aux._log[1], NotImplementedError)
        # Test RuntimeError raised when thread otherwise fails
        self.aux.refresh_rate = self.services().timeout = 0  # Wait for 0 seconds
        self.assertRaises(RuntimeError, self.aux.push, 'EXPINIT', wait=True)


if __name__ == '__main__':
    unittest.main()
