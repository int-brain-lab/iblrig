"""Tests for NetworkSession class."""
import unittest
from unittest.mock import patch, call, ANY
from datetime import date

from one.api import ONE
from iblrig.base_tasks import NetworkSession, EmptySession
from iblrig.test.base import TaskArgsMixin
from iblutil.io import net


class NetworkSession(EmptySession, NetworkSession):
    protocol_name = '_ibl_network_session'

    def register_to_alyx(self):
        pass


class TestNetworkTask(unittest.TestCase, TaskArgsMixin):
    """Test a situation where the main sync is on a different computer."""

    def setUp(self):
        self.clients = {'ZcanImage': 'udp://192.168.0.1', 'cameras': 'udp://192.168.0.2'}
        self.get_task_kwargs()
        self.task_kwargs['one'] = ONE(silent=True, mode='local')
        self.task_kwargs['remote_rigs'] = self.clients
        self.task_kwargs['hardware_settings']['MAIN_SYNC'] = False
        # An experiment reference for our remote sync to return
        self.sequence = 2
        self.exp_ref = '_'.join(map(str, (date.today(), self.sequence, self.task_kwargs['subject'])))

    def _prepare_mock(self, aux_mock):
        """Prepare default responses for mock Auxiliary object."""
        aux = aux_mock({})
        aux.is_connected = True
        aux.push.return_value = {
            'ZcanImage': [int(net.base.ExpStatus.RUNNING), {'main_sync': True, 'exp_ref': self.exp_ref}],
            'cameras': [int(net.base.ExpStatus.CONNECTED), {'main_sync': False, 'exp_ref': None}]
        }
        aux_mock.reset_mock()  # reset previous call
        return aux

    @patch('iblrig.net.Auxiliaries', autospec=True)
    def test_mixin_as_main_sync(self, aux):
        """Test main sync check.

        When passing in remote_rigs arg the behaviour computer must not be the main sync.
        """
        aux.is_connected = True
        # Should raise NotImplementedError
        self.task_kwargs['hardware_settings']['MAIN_SYNC'] = True
        self.assertRaises(NotImplementedError, NetworkSession, **self.task_kwargs)

    @patch('iblrig.net.Auxiliaries', autospec=True)
    def test_communicate(self, aux_mock):
        """Test communicate method, namely the raise_on_exception kwarg."""
        aux = self._prepare_mock(aux_mock)
        task = NetworkSession(**self.task_kwargs)
        aux.push.return_value = TimeoutError('FOO')
        with self.assertLogs('iblrig.base_tasks', 'ERROR'):
            r = task.communicate('EXPSTART', self.exp_ref, raise_on_exception=False)
            self.assertIsInstance(r, TimeoutError)
        aux.close.assert_not_called()
        self.assertRaises(TimeoutError, task.communicate, 'EXPSTART', self.exp_ref, raise_on_exception=True)
        aux.close.assert_called()

    @patch('iblrig.net.Auxiliaries', autospec=True)
    def test_network_init(self, aux_mock):
        """Test init routine, namely the update of paths from remote rig."""
        aux = self._prepare_mock(aux_mock)
        task = NetworkSession(**self.task_kwargs)
        aux_mock.assert_called_with(self.clients)
        expected = {'date': (date.today()), 'subject': self.task_kwargs['subject'], 'sequence': self.sequence}
        self.assertEqual(expected, task.exp_ref)
        # Should initialize other rigs with main sync exp ref
        aux.push.assert_called_with('EXPINIT', {'exp_ref': self.exp_ref}, wait=True)
        # Should have updated the session path
        self.assertEqual(self.sequence, int(task.paths.SESSION_FOLDER.name))

        # Check remote rigs as list input
        aux_mock.reset_mock()
        task_kwargs = self.task_kwargs | {'remote_rigs': list(self.clients)}
        # Should raise when list of rig names provided with no remote devices file to determine URIs
        self.assertRaises(ValueError, NetworkSession, **task_kwargs)
        # With a remote devices file, the subject of names provided should be sent to Auxiliaries object
        with patch('iblrig.net.get_remote_devices', return_value={'foo': 'udp://192.168.0.5', **self.clients}):
            task = NetworkSession(**self.task_kwargs)
            aux_mock.assert_called_with(self.clients)

        # Check errors
        # Remote subject doesn't match
        task_kwargs = self.task_kwargs | {'subject': 'foobar'}
        self.assertRaises(ValueError, NetworkSession, **task_kwargs)
        # Append doesn't match
        task_kwargs = self.task_kwargs | {'append': True}
        self.assertRaises(ValueError, NetworkSession, **task_kwargs)  # append should be False
        task.paths.SESSION_FOLDER.mkdir(parents=True)
        task.paths.SESSION_FOLDER.joinpath(task.paths.TASK_COLLECTION).mkdir()
        self.assertRaises(ValueError, NetworkSession, **self.task_kwargs)  # append should be True
        task_2 = NetworkSession(**task_kwargs)
        self.assertEqual('raw_task_data_01', task_2.paths.TASK_COLLECTION)
        task.paths.SESSION_FOLDER.joinpath(task.paths.TASK_COLLECTION).rmdir()
        # Date doesn't match
        aux.push.return_value['ZcanImage'][1]['exp_ref'] = '2020-01-01' + self.exp_ref[10:]
        self.assertRaises(RuntimeError, NetworkSession, **self.task_kwargs)

    @patch('iblrig.net.Auxiliaries', autospec=True)
    def test_full_run(self, aux_mock):
        """Test network activity over entire session."""
        aux = self._prepare_mock(aux_mock)
        task = NetworkSession(**self.task_kwargs)
        task.run()
        expected = [call('EXPINFO', 'CONNECTED', ANY, wait=True),
                    call('EXPINIT', {'exp_ref': self.exp_ref}, wait=True),
                    call('EXPSTART', self.task_kwargs['one'].ref2dict(self.exp_ref), wait=True),
                    call('EXPEND', wait=True)]
        aux.push.assert_has_calls(expected, any_order=True)
        # Expect subject key in exp info structure
        ((*_, info), _), *_ = aux.push.call_args_list
        self.assertEqual(self.task_kwargs['subject'], info.get('subject'))
        aux.close.assert_called()

        aux_mock.reset_mock()
        # Test run errors
        with patch.object(task, '_run', side_effect=RuntimeError('Bpod failed')):
            self.assertRaises(RuntimeError, task.run)  # should re-raise runtime error after cleanup
        aux.push.assert_any_call('EXPSTART', self.task_kwargs['one'].ref2dict(self.exp_ref), wait=True)
        aux.push.assert_called_with(net.base.ExpMessage.EXPINTERRUPT, ANY, wait=True)
        (_, ex), kwargs = aux.push.call_args
        self.assertCountEqual(('error', 'message', 'traceback', 'file', 'line_no'), ex)
        self.assertEqual('RuntimeError', ex['error'])
        self.assertEqual('Bpod failed', ex['message'])
        aux.close.assert_called()
        # Test communication error
        aux_mock.reset_mock()
        aux.push.side_effect = [aux.push.return_value, TimeoutError('FOO'), {'ZcanImage': [], 'cameras': []}]
        self.assertRaises(TimeoutError, task.run)  # should re-raise timeout error after cleanup
        aux.close.assert_called()

    @patch('iblrig.net.Auxiliaries.push')
    def test_inactive_networks(self, push_mock):
        """Test behaviour when no remote rigs provided."""
        task_kwargs = self.task_kwargs | {'remote_rigs': {}}
        task = NetworkSession(**task_kwargs)
        self.assertFalse(task.remote_rigs.is_connected)
        self.assertTrue(task.remote_rigs.is_running)
        task.run()
        self.assertIsNone(task.remote_rigs.services)
        push_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
