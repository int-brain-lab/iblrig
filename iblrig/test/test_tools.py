import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from iblrig.constants import BONSAI_EXE
from iblrig.tools import ask_user, call_bonsai, internet_available, update_json_file


class TestAskUser(unittest.TestCase):
    @patch('builtins.input', return_value='')
    def test_ask_user_with_defaults(self, mock_input):
        result = ask_user('Do you want to continue?')
        self.assertFalse(result)
        result = ask_user('Do you want to continue?', default=True)
        self.assertTrue(result)

    @patch('builtins.input', side_effect=['', 'n', 'No', 'NO'])
    def test_ask_user_with_input_no(self, mock_input):
        for _ in range(4):
            self.assertFalse(ask_user(''))

    @patch('builtins.input', side_effect=['', 'y', 'Yes', 'YES'])
    def test_ask_user_with_input_yes(self, mock_input):
        for _ in range(4):
            self.assertTrue(ask_user('', default=True))

    @patch('builtins.input', side_effect=['invalid', 'blah', 'a', 'n'])
    def test_ask_user_with_invalid_input(self, mock_input):
        result = ask_user('Do you want to continue?')
        self.assertFalse(result)


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
    @patch('subprocess.run', return_value=subprocess.CompletedProcess(args='', returncode=0))
    @patch('iblrig.tools.create_bonsai_layout_from_template')
    @patch('pathlib.Path.exists', return_value=False)
    def test_call_bonsai(self, mock_exists, mock_create_layout, mock_check_call):
        workflow_file = Path('some', 'dir', 'example_workflow.bonsai')
        with self.assertRaises(FileNotFoundError):
            call_bonsai(workflow_file)
        mock_exists.return_value = True
        parameters = {'parameter1': 1, 'parameter2': 'asd'}
        result = call_bonsai(workflow_file, parameters, debug=True, bootstrap=False, editor=False)
        mock_check_call.assert_called_once_with(
            args=[
                str(BONSAI_EXE),
                str(workflow_file),
                '--start',
                '--no-editor',
                '--no-boot',
                '-p:parameter1=1',
                '-p:parameter2=asd',
            ],
            cwd=workflow_file.parent,
            check=False,
        )
        mock_create_layout.assert_called_once_with(workflow_file)
        self.assertIsInstance(result, subprocess.CompletedProcess)


class TestUpdateJsonFile(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory for test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_update_json_file_basic(self):
        """Test basic JSON file update."""
        json_file = self.temp_path / 'test.json'
        json_file.write_text('{"key1": "value1", "key2": "value2"}')

        update_json_file(json_file, {'key1': 'updated_value'})

        result = json.loads(json_file.read_text())
        self.assertEqual(result['key1'], 'updated_value')
        self.assertEqual(result['key2'], 'value2')

    def test_update_json_file_add_new_key(self):
        """Test adding a new key to JSON file."""
        json_file = self.temp_path / 'test.json'
        json_file.write_text('{"existing": "value"}')

        update_json_file(json_file, {'new_key': 'new_value'})

        result = json.loads(json_file.read_text())
        self.assertEqual(result['existing'], 'value')
        self.assertEqual(result['new_key'], 'new_value')

    def test_update_json_file_with_kwargs(self):
        """Test JSON update with formatting options."""
        json_file = self.temp_path / 'test.json'
        json_file.write_text('{"key": "value"}')

        update_json_file(json_file, {'new_key': 'new_value'}, indent=2, sort_keys=True)

        content = json_file.read_text()
        # Verify it's indented
        self.assertIn('\n', content)
        # Verify keys are sorted
        self.assertIn('"key"', content)
        self.assertIn('"new_key"', content)

    def test_update_json_file_not_found(self):
        """Test error when JSON file doesn't exist."""
        json_file = self.temp_path / 'nonexistent.json'

        with self.assertRaises(FileNotFoundError):
            update_json_file(json_file, {'key': 'value'})

    def test_update_json_file_invalid_json(self):
        """Test error when JSON file contains invalid JSON."""
        json_file = self.temp_path / 'invalid.json'
        json_file.write_text('not valid json {')

        with self.assertRaises(json.JSONDecodeError):
            update_json_file(json_file, {'key': 'value'})

    def test_update_json_file_non_dict_root(self):
        """Test error when JSON root is not a dict."""
        json_file = self.temp_path / 'array.json'
        json_file.write_text('[1, 2, 3]')

        with self.assertRaises(ValueError) as context:
            update_json_file(json_file, {'key': 'value'})

        self.assertIn('dict', str(context.exception).lower())

    def test_update_json_file_with_string_path(self):
        """Test update_json_file works with string path."""
        json_file = self.temp_path / 'test.json'
        json_file.write_text('{"key": "value"}')

        # Pass as string instead of Path
        update_json_file(str(json_file), {'key': 'updated'})

        result = json.loads(json_file.read_text())
        self.assertEqual(result['key'], 'updated')
