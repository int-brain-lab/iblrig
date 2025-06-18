import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import iblrig.ephys
from iblrig.test.base import TEST_DB
from iblutil.io import net
from iblutil.util import Bunch


class TestFinalizeEphysSession(unittest.TestCase):
    def test_neuropixel24_micromanipulator(self):
        probe_dict = {'x': 2594.2, 'y': -3123.7, 'z': -711, 'phi': 0 + 15, 'theta': 15, 'depth': 1250.4, 'roll': 0}
        trajectories = iblrig.ephys.neuropixel24_micromanipulator_coordinates(probe_dict, 'probe01')
        a = {
            'probe01a': {'x': 2594.2, 'y': -3123.7, 'z': -231.33599999999996, 'phi': 15, 'theta': 15, 'depth': 1250.4, 'roll': 0},
            'probe01b': {
                'x': 2645.963809020504,
                'y': -3316.8851652578132,
                'z': -255.136,
                'phi': 15,
                'theta': 15,
                'depth': 1226.6000000000001,
                'roll': 0,
            },
            'probe01c': {
                'x': 2697.727618041008,
                'y': -3510.070330515627,
                'z': -302.73599999999993,
                'phi': 15,
                'theta': 15,
                'depth': 1179.0,
                'roll': 0,
            },
            'probe01d': {
                'x': 2749.4914270615122,
                'y': -3703.255495773441,
                'z': -350.336,
                'phi': 15,
                'theta': 15,
                'depth': 1131.4,
                'roll': 0,
            },
        }
        assert trajectories == a


class TestPrepareEphysSessionNetworked(unittest.IsolatedAsyncioTestCase):
    """Test the main_v8_networked function."""

    def setUp(self):
        """Set up keyboard input and settings mocks."""
        # Set up keyboad input mock
        # When we set self.keyboard to a non-empty string, the test function should interpret this as
        # keyboard input and stop the session (i.e. close the communicator and return)
        self.keyboard = ''
        read_stdin = patch('iblrig.ephys.read_stdin')
        self.addCleanup(read_stdin.stop)
        read_stdin_mock = read_stdin.start()

        async def _stdin():
            if self.keyboard:
                yield self.keyboard

        read_stdin_mock.side_effect = _stdin

        # Set up settings mock
        tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(tmp.name)
        (local := self.tmpdir.joinpath('local')).mkdir()
        (remote := self.tmpdir.joinpath('remote')).mkdir()
        (remote_subjects := remote.joinpath('subjects')).mkdir()
        self.settings = Bunch(
            iblrig_local_data_path=local, iblrig_remote_data_path=remote, iblrig_remote_subjects_path=remote_subjects
        )
        m = patch('iblrig.ephys.load_pydantic_yaml', return_value=self.settings)
        m.start()
        self.addCleanup(m.stop)
        self.addr = '192.168.0.5:99998'  # Fake address of the behaviour rig

    async def asyncSetUp(self):
        """Set up communicator mock.

        To side-step UDP communication, we mock the communicator and simulate the messages that
        would be sent by the behaviour rig, then assert that the response methods are called with
        the expected arguments.
        """
        self.communicator = AsyncMock(spec=iblrig.ephys.net.app.EchoProtocol)
        self.communicator.is_connected = True
        m = patch('iblrig.ephys.get_server_communicator', return_value=(self.communicator, None))
        m.start()
        self.addCleanup(m.stop)

    async def test_standard_message_sequence(self):
        """Test the main_v8_networked function with the usual sequence of behaviour rig messages."""
        # Create some mock behaviour rig messages
        ref = f'{date.today()}_1_foo'
        info_msg = ((net.base.ExpStatus.CONNECTED, {'subject_name': 'foo'}), self.addr, net.base.ExpMessage.EXPINFO)
        init_msg = ([{'exp_ref': ref}], self.addr, net.base.ExpMessage.EXPINIT)
        start_msg = ((ref, {}), self.addr, net.base.ExpMessage.EXPSTART)
        status_msg = (net.base.ExpStatus.RUNNING, self.addr, net.base.ExpMessage.EXPSTATUS)
        # This is the order in which the messages are expected to be sent (excluding status)
        self.messages = (info_msg, init_msg, start_msg, status_msg)

        messages = self._iterate_messages()
        self.communicator.on_event.side_effect = lambda evt: next(messages)
        await iblrig.ephys.main_v8_networked('foo', debug=True)

        # The on_event method is awaited at first then each time a message is received
        self.communicator.on_event.assert_awaited_with(net.base.ExpMessage.any())
        self.assertEqual(1 + len(self.messages), self.communicator.on_event.await_count)

        # Check that the expected methods were called with the expected arguments
        kwargs = dict(addr=self.addr)
        expected_responses = [
            ('info', (net.base.ExpStatus.RUNNING, {'exp_ref': ref, 'main_sync': True}), kwargs),
            ('init', ({'exp_ref': ref, 'status': net.base.ExpStatus.RUNNING},), kwargs),
            ('start', ({'subject': 'foo', 'date': date.today(), 'sequence': 1},), kwargs),
            ('status', (net.base.ExpStatus.RUNNING,), kwargs),
            ('close', (), {}),  # should be called after the last message (when keyboad input is simulated)
        ]
        # Check odd method calls as even ones are the on_event calls
        actual_reponses = map(tuple, self.communicator.method_calls[1::2])
        for expected, actual in zip(expected_responses, actual_reponses, strict=False):
            self.assertEqual(expected, actual)

        # Check that the local and remote sessions were created
        expected = [
            f'local/foo/{date.today()}/001/transfer_me.flag',
            f'local/foo/{date.today()}/001/_ibl_experiment.description_ephys.yaml',
            f'remote/subjects/foo/{date.today()}/001/_devices/{date.today()}_1_foo@ephys.status_pending',
            f'remote/subjects/foo/{date.today()}/001/_devices/{date.today()}_1_foo@ephys.yaml',
        ]
        self.assertCountEqual(map(self.tmpdir.joinpath, expected), self.tmpdir.rglob('*.*'))
        # Should have created the raw ephys folders
        self.assertEqual(2, len(list(self.tmpdir.glob(f'local/foo/{date.today()}/001/raw_ephys_data/probe??'))))

    async def test_abort_session(self):
        """Test the main_v8_networked function with misc events and user 'abort' input."""
        # Create some mock behaviour rig messages where the behaviour rig runs subject 'bar' instead of 'foo'
        # No exception should be raised (this happens at the behaviour rig) but this should be logged
        ref = f'{date.today()}_1_bar'
        info_msg = ((net.base.ExpStatus.CONNECTED, {'subject_name': 'bar'}), self.addr, net.base.ExpMessage.EXPINFO)
        init_msg = ([{'exp_ref': ref}], self.addr, net.base.ExpMessage.EXPINIT)
        start_msg = ((ref, {}), self.addr, net.base.ExpMessage.EXPSTART)
        interrupt_msg = ((), self.addr, net.base.ExpMessage.EXPINTERRUPT)
        cleanup_msg = ((), self.addr, net.base.ExpMessage.EXPCLEANUP)
        self.messages = (info_msg, init_msg, start_msg, interrupt_msg, cleanup_msg)

        messages = self._iterate_messages(keyboard_input='ABORT\n')
        self.communicator.on_event.side_effect = lambda evt: next(messages)
        # Should log exp ref mismatch
        with self.assertLogs('iblrig.ephys', level='CRITICAL'), patch('builtins.input', return_value='y') as mock_input:
            await iblrig.ephys.main_v8_networked('foo', debug=True)
            mock_input.assert_called_once()

        # The on_event method is awaited at first then each time a message is received
        self.communicator.on_event.assert_awaited_with(net.base.ExpMessage.any())
        self.assertEqual(1 + len(self.messages), self.communicator.on_event.await_count)

        # Check that the expected methods were called with the expected arguments
        kwargs = dict(addr=self.addr)
        ref = f'{date.today()}_1_foo'
        expected_responses = [
            ('info', (net.base.ExpStatus.RUNNING, {'exp_ref': ref, 'main_sync': True}), kwargs),
            ('init', ({'exp_ref': ref, 'status': net.base.ExpStatus.RUNNING},), kwargs),
            ('start', ({'subject': 'foo', 'date': date.today(), 'sequence': 1},), kwargs),
            ('confirmed_send', ((net.base.ExpMessage.EXPINTERRUPT, {'status': net.base.ExpStatus.RUNNING}),), kwargs),
            ('confirmed_send', ((net.base.ExpMessage.EXPCLEANUP, {'status': net.base.ExpStatus.RUNNING}),), kwargs),
            ('close', (), {}),  # should be called after the last message (when keyboad input is simulated)
        ]
        # Check odd method calls as even ones are the on_event calls
        for expected, actual in zip(expected_responses, map(tuple, self.communicator.method_calls[1::2]), strict=False):
            self.assertEqual(expected, actual)

        # Check that the local and remote sessions were removed
        self.assertFalse(any(self.tmpdir.rglob('*.*')))
        self.assertFalse(self.tmpdir.joinpath(f'local/foo/{date.today()}/001').exists())

        # Check behaviour when user does not confirm cleanup
        self.communicator.reset_mock()  # _iterate_messages asserts no methods were called yet
        messages = self._iterate_messages(keyboard_input='ABORT\n')
        self.communicator.on_event.side_effect = lambda evt: next(messages)
        with patch('builtins.input', return_value='') as mock_input:
            await iblrig.ephys.main_v8_networked('foo', debug=True)
            mock_input.assert_called_once()
        self.assertTrue(any(self.tmpdir.rglob('*.*')))
        self.assertTrue(self.tmpdir.joinpath(f'local/foo/{date.today()}/001').exists())

    async def test_alyx_request(self):
        """Test the main_v8_networked function alyx request message."""
        # Create some mock behaviour rig messages that request and provide Alyx credentials
        alyx_req = ((None, {}), self.addr, net.base.ExpMessage.ALYX)
        alyx_mes = ((TEST_DB['base_url'], {'test_user': {'token': 't0k3n'}}), self.addr, net.base.ExpMessage.ALYX)
        # Behaviour should be thus:
        #  1. Request not processed as Alyx offline by default
        #  2. Alyx object updated with remote token
        #  3. Request processed with updated Alyx object (now logged in)
        self.messages = (alyx_req, alyx_mes, alyx_req)

        messages = self._iterate_messages()
        self.communicator.on_event.side_effect = lambda evt: next(messages)
        with patch('iblrig.ephys.update_alyx_token', wraps=iblrig.ephys.update_alyx_token) as m:
            await iblrig.ephys.main_v8_networked('foo', debug=True)
            m.assert_called_once()

        # Check that the expected methods were called with the expected arguments
        self.communicator.alyx.assert_awaited_once()
        (alyx,), addr = self.communicator.alyx.call_args
        self.assertTrue(alyx.is_logged_in)
        self.assertEqual(TEST_DB['base_url'], alyx.base_url)
        self.assertEqual({'token': 't0k3n'}, alyx._token)

    def _iterate_messages(self, keyboard_input='\n'):
        """Yield behaviour rig UDP messages with added side effect simulating keyboard input after."""
        # When first called we shouold not have awaited any methods on the communicator yet
        for method in ('info', 'init', 'start', 'status', 'alyx', 'confirmed_send'):
            getattr(self.communicator, method).assert_not_awaited()
        # Yeild the messages in order
        for msg in self.messages:  # noqa: UP028
            yield msg  # ruff complains here but the suggested `yield from` does not work
        # After the last message is processed, terminate by simulating keyboard input
        self.keyboard = keyboard_input
        yield self.messages[-1]
