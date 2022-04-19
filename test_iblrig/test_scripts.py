import json
import os
import pathlib
import tempfile
import unittest


# TODO: Flesh out script testing in the future?
class TestScripts(unittest.TestCase):

    def test_transfer_rig_data(self):
        # Ensure transfer_rig_data.py exists
        current_path = pathlib.Path(__file__).parent.absolute()
        transfer_rig_data_script_loc = current_path.parent / 'scripts' / 'transfer_rig_data.py'
        self.assertTrue(os.path.exists(transfer_rig_data_script_loc))

        # Create local and remote temp directories, local session path, flags, and taskSettings
        local_temp_dir = tempfile.TemporaryDirectory()
        remote_temp_dir = tempfile.TemporaryDirectory()
        local_subjects_dir = pathlib.Path(local_temp_dir.name) / 'Subjects'
        remote_subjects_dir = pathlib.Path(remote_temp_dir.name) / 'Subjects'
        local_session_location = pathlib.Path(local_subjects_dir) \
                                 / '_iblrig_fake_mouse' / '1970-01-01' / '001'
        local_raw_video_location = pathlib.Path(local_session_location) / 'raw_video_data'
        local_raw_behavior_location = pathlib.Path(local_session_location) / 'raw_behavior_data'
        task_settings_data = {'PYBPOD_BOARD': '_iblrig_mainenlab_behavior_2'}
        try:
            # add passive ephys data
            os.makedirs(local_subjects_dir, exist_ok=True)
            os.makedirs(remote_subjects_dir, exist_ok=True)
            os.makedirs(local_session_location, exist_ok=True)
            os.makedirs(local_raw_video_location, exist_ok=True)
            os.makedirs(local_raw_behavior_location, exist_ok=True)
            local_session_location.joinpath('transfer_me.flag').touch()
            local_raw_video_location.joinpath('_iblrig_leftCamera.raw.avi').touch()
            local_raw_behavior_location.joinpath('_iblrig_micData.raw.wav').touch()
            with open(local_raw_behavior_location / '_iblrig_taskSettings.raw.json', 'w') \
                    as task_settings:
                json.dump(task_settings_data, task_settings)
        except OSError:
            print('Could not create temp directories and/or flag files.')

        # Call transfer_rig_data.py script
        os.system(f"python "
                  f"{transfer_rig_data_script_loc} {local_subjects_dir} {remote_subjects_dir}")

        # verify files moved
        remote_session_location = pathlib.Path(remote_subjects_dir) \
                                  / '_iblrig_fake_mouse' / '1970-01-01' / '001'
        remote_raw_video_location = pathlib.Path(remote_session_location) / 'raw_video_data'
        remote_raw_video_left_camera = pathlib.Path(remote_raw_video_location) \
                                       / '_iblrig_leftCamera.raw.avi'
        remote_raw_behavior_location = pathlib.Path(remote_session_location) / 'raw_behavior_data'
        remote_raw_behavior_mic_data = pathlib.Path(remote_raw_behavior_location) \
                                       / '_iblrig_micData.raw.wav'
        remote_raw_session_flag = pathlib.Path(remote_session_location) / 'raw_session.flag'
        self.assertTrue(remote_raw_video_left_camera.exists())
        self.assertTrue(remote_raw_behavior_mic_data.exists())
        self.assertTrue(remote_raw_session_flag.exists())

        # Test for ephys rig, generate _iblrig_taskSettings.raw.json
        # task_settings_data = {'PYBPOD_BOARD': '_iblrig_mainenlab_ephys_0'}
        # try:
        #     with open(local_raw_behavior_location / '_iblrig_taskSettings.raw.json', 'w') \
        #             as task_settings:
        #         json.dump(task_settings_data, task_settings)
        # except OSError:
        #     print('Could not create json files')
        #
        # # Verify raw_session.flag file was removed
        # # log.info(f"Removing raw_session.flag file; ephys behavior rig detected")

        # Cleanup of temp directories and files
        local_temp_dir.cleanup()
        remote_temp_dir.cleanup()