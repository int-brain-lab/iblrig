import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile

import yaml
from iblutil.util import Bunch

from iblrig import video


class TestDownloadFunction(unittest.TestCase):
    @patch('one.webclient.AlyxClient.download_file', return_value=('mocked_tmp_file', 'mocked_md5_checksum'))
    @patch('os.rename', return_value=None)
    def test_download_from_alyx_or_flir(self, mock_os_rename, mock_alyx_download):
        asset = 123
        filename = 'test_file.txt'

        # Call the function
        result = video._download_from_alyx_or_flir(asset, filename, 'mocked_md5_checksum')

        # Assertions
        expected_out_file = Path.home().joinpath('Downloads', filename)
        self.assertEqual(result, expected_out_file)
        mock_alyx_download.assert_called_once_with(
            f'resources/spinnaker/{filename}', target_dir=Path(expected_out_file.parent), clobber=True, return_md5=True
        )
        mock_os_rename.assert_called_once_with('mocked_tmp_file', expected_out_file)


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.old_params = Bunch({
            'DATA_FOLDER_PATH': r'D:\iblrig_data\Subjects',
            'REMOTE_DATA_FOLDER_PATH': r'\\iblserver.champalimaud.pt\ibldata\Subjects',
            'BODY_CAM_IDX': 0,
            'LEFT_CAM_IDX': 3,
            'RIGHT_CAM_IDX': 2,
        })
        params_dict_mock = patch('iblrig.video.load_params_dict', return_value=self.old_params)
        params_dict_mock.start()
        self.addCleanup(params_dict_mock.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._settings = {}
        for file in ('iblrig', 'hardware'):
            filepath = Path(video.__file__).parents[1].joinpath('settings', f'{file}_settings.yaml')
            if filepath.exists():
                with open(filepath, 'r') as fp:
                    self._settings[filepath] = fp.read()

    @patch('iblrig.video.params.getfile')
    def test_patch_old_params(self, getfile_mock):
        (old_file := Path(self.tmp.name, '.videopc_params')).touch()
        getfile_mock.return_value = old_file
        video.patch_old_params(remove_old=False)
        patched = self._load_patched_settings()  # Load the patched settings
        self.assertIn('device_cameras', patched['hardware_settings'])
        for cam, idx in dict(left=3, right=2, body=0).items():
            self.assertEqual(idx, patched['hardware_settings']['device_cameras'][cam]['INDEX'])
        self.assertEqual(r'D:\iblrig_data', patched['iblrig_settings']['iblrig_local_data_path'])
        self.assertEqual(r'\\iblserver.champalimaud.pt\ibldata', patched['iblrig_settings']['iblrig_remote_data_path'])
        self.assertTrue(old_file.exists(), 'failed to keep old settings file')

        # Check this works without settings files
        for filepath in self._settings:
            filepath.unlink()
        # Test insertion of 'subjects' path key if old location doesn't end in 'Subjects'
        for key in ('DATA_FOLDER_PATH', 'REMOTE_DATA_FOLDER_PATH'):
            self.old_params[key] = self.old_params[key].replace('Subjects', 'foobar')
        video.patch_old_params(remove_old=True)
        patched = self._load_patched_settings()  # Load the patched settings
        self.assertEqual(self.old_params['DATA_FOLDER_PATH'], patched['iblrig_settings']['iblrig_local_subjects_path'])
        self.assertEqual(self.old_params['REMOTE_DATA_FOLDER_PATH'], patched['iblrig_settings']['iblrig_remote_subjects_path'])
        self.assertFalse(old_file.exists(), 'failed to remove old settings file')

        video.patch_old_params()  # Shouldn't raise after removing old settings

    def _load_patched_settings(self):
        patched = {}
        for settings_file in self._settings:
            with open(settings_file, 'r') as fp:
                patched[settings_file.stem] = yaml.safe_load(fp)
        return patched

    def tearDown(self):
        for filepath, data in getattr(self, '_settings', {}).items():
            with open(filepath, 'w') as fp:
                fp.write(data)


if __name__ == '__main__':
    unittest.main()
