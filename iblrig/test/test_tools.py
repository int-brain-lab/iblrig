import unittest
from pathlib import Path
from unittest.mock import patch

from iblrig.tools import ask_user, call_bonsai, internet_available, static_vars


class TestAskUser(unittest.TestCase):
    @patch('builtins.input', return_value='')
    def test_ask_user_with_defaults(self, mock_input):
        result = ask_user('Do you want to continue?')
        self.assertFalse(result)
        result = ask_user('Do you want to continue?', default=True)
        self.assertTrue(result)

    @patch('builtins.input', side_effect=['', 'n', 'No', 'NO'])
    def test_ask_user_with_input_no(self, mock_input):
        for i in range(4):
            self.assertFalse(ask_user(''))

    @patch('builtins.input', side_effect=['', 'y', 'Yes', 'YES'])
    def test_ask_user_with_input_yes(self, mock_input):
        for i in range(4):
            self.assertTrue(ask_user('', default=True))

    @patch('builtins.input', side_effect=['invalid', 'blah', 'a', 'n'])
    def test_ask_user_with_invalid_input(self, mock_input):
        result = ask_user('Do you want to continue?')
        self.assertFalse(result)


class TestStaticVarsDecorator(unittest.TestCase):
    def test_static_vars_decorator(self):
        @static_vars(var1=1, var2='test')
        def test_function():
            return test_function.var1, test_function.var2

        self.assertEqual(test_function(), (1, 'test'))
        test_function.var1 = 42
        test_function.var2 = 'modified'
        self.assertEqual(test_function(), (42, 'modified'))


class TestInternetAvailableFunction(unittest.TestCase):
    @patch('socket.socket')
    def test_internet_available_with_internet(self, mock_socket):
        mock_socket.return_value.__enter__.return_value.connect.side_effect = None
        result = internet_available(force_update=True)
        self.assertTrue(result)

    @patch('socket.socket')
    def test_internet_available_without_internet(self, mock_socket):
        mock_socket.return_value.__enter__.return_value.connect.side_effect = OSError
        result = internet_available(force_update=True)
        self.assertFalse(result)

    @patch('socket.socket')
    def test_internet_available_with_cached_result(self, mock_socket):
        mock_socket.return_value.__enter__.return_value.connect.side_effect = None
        result1 = internet_available(force_update=True)
        self.assertTrue(result1)
        mock_socket.return_value.__enter__.return_value.connect.side_effect = OSError
        result2 = internet_available(force_update=False)
        self.assertTrue(result2)


class TestCallBonsai(unittest.TestCase):
    @patch('subprocess.check_call', return_value=0)
    @patch('iblrig.tools.create_bonsai_layout_from_template')
    @patch('iblrig.tools.get_bonsai_path', return_value=Path('path', 'to', 'Bonsai.exe'))
    @patch('pathlib.Path.exists', return_value=False)
    def test_call_bonsai(self, mock_exists, mock_get_bonsai_path, mock_create_layout, mock_check_call):
        bonsai_path = mock_get_bonsai_path.return_value
        workflow_file = Path('some', 'dir', 'example_workflow.bonsai')
        with self.assertRaises(FileNotFoundError):
            call_bonsai(workflow_file)
        mock_exists.return_value = True
        args = ['arg1', 'arg2']
        result = call_bonsai(workflow_file, args, debug=True, bootstrap=False, editor=False)
        mock_check_call.assert_called_once_with(
            executable=bonsai_path,
            args=['--start', '--no-editor', '--no-boot', 'arg1', 'arg2', Path(workflow_file)],
            cwd=workflow_file.parent,
        )
        mock_create_layout.assert_called_once_with(workflow_file)
        mock_get_bonsai_path.assert_called_once()
        self.assertEqual(result, 0)
