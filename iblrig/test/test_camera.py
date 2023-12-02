import unittest
from unittest.mock import patch
from pathlib import Path


class TestDownloadFunction(unittest.TestCase):
    @patch('one.webclient.AlyxClient.download_file', return_value=('mocked_tmp_file', 'mocked_md5_checksum'))
    @patch('os.rename', return_value=None)
    def test_download_from_alyx_or_flir(self, mock_os_rename, mock_alyx_download):
        from iblrig.camera import _download_from_alyx_or_flir

        asset = 123
        filename = 'test_file.txt'

        # Call the function
        result = _download_from_alyx_or_flir(asset, filename, 'mocked_md5_checksum')

        # Assertions
        expected_out_file = Path.home().joinpath('Downloads', filename)
        self.assertEqual(result, expected_out_file)
        mock_alyx_download.assert_called_once_with(
            f'resources/spinnaker/{filename}', target_dir=Path(expected_out_file.parent), clobber=True, return_md5=True
        )
        mock_os_rename.assert_called_once_with('mocked_tmp_file', expected_out_file)


if __name__ == '__main__':
    unittest.main()
