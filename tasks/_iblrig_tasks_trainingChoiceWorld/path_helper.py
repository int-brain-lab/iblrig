# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, November 14th 2018, 10:40:43 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 14-11-2018 10:41:08.088
import datetime
import json
import os
import subprocess
from pathlib import Path
from sys import platform


class SessionPathCreator(object):
    # add subject name and protocol (maybe have a metadata struct)
    def __init__(self, iblrig_folder, iblrig_data_folder, subject_name,
                 protocol=False, board=False, make=False):
        if platform == 'linux':
            self.IBLRIG_FOLDER = '/home/nico/Projects/IBL/IBL-github/iblrig'
        else:
            self.IBLRIG_FOLDER = str(Path(iblrig_folder))
        self.IBLRIG_COMMIT_HASH = self._get_iblrig_commit_hash()
        self.IBLRIG_VERSION_TAG = self._get_iblrig_version_tag()

        self.IBLRIG_PARAMS_FOLDER = str(
            Path(self.IBLRIG_FOLDER).parent / 'iblrig_params')
        self.IBLRIG_DATA_FOLDER = self._iblrig_data_folder_init(
            self.IBLRIG_FOLDER, iblrig_data_folder)
        self.IBLRIG_DATA_SUBJECTS_FOLDER = str(
            Path(self.IBLRIG_DATA_FOLDER) / 'Subjects')
        self.SOUND_STIM_FOLDER = os.path.join(
            self.IBLRIG_FOLDER, 'sound_stim', 'sounds')
        self.VISUAL_STIM_FOLDER = os.path.join(
            self.IBLRIG_FOLDER, 'visual_stim', 'Gabor2D')
        self.VIDEO_RECORDING_FOLDER = os.path.join(
            self.IBLRIG_FOLDER, 'camera', 'camera_recordings')
        self.VISUAL_STIMULUS_FILE = os.path.join(
            self.IBLRIG_FOLDER, 'visual_stim', 'Gabor2D', 'Gabor2D.bonsai')
        self.VIDEO_RECORDING_FILE = os.path.join(
            self.IBLRIG_FOLDER, 'camera', 'camera_recordings',
            'one_camera.bonsai')
        self.SUBJECT_NAME = subject_name
        self.SUBJECT_FOLDER = os.path.join(
            self.IBLRIG_DATA_SUBJECTS_FOLDER, self.SUBJECT_NAME)
        self.SESSION_DATETIME = datetime.datetime.now()
        self.SESSION_DATE = self.SESSION_DATETIME.date().isoformat()
        self.SESSION_DATE_FOLDER = os.path.join(
            self.SUBJECT_FOLDER, self.SESSION_DATE)

        self.SESSION_NUMBER = self._session_number()

        self.SESSION_FOLDER = os.path.join(
            self.SESSION_DATE_FOLDER, self.SESSION_NUMBER)
        self.SESSION_RAW_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_behavior_data')
        self.SESSION_RAW_VIDEO_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_video_data')
        self.SESSION_RAW_EPHYS_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_ephys_data')
        self.SESSION_RAW_IMAGING_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_imaging_data')

        self.SESSION_COMPOUND_NAME = '{}'.format(os.path.sep).join(
            [self.SUBJECT_NAME, self.SESSION_DATE, self.SESSION_NUMBER,
             protocol, board])

        self.BASE_FILENAME = '_iblrig_task'
        self.SETTINGS_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                               self.BASE_FILENAME +
                                               'Settings.raw.json')
        self.DATA_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                           self.BASE_FILENAME +
                                           'Data.raw.jsonable')

        self.LATEST_WATER_CALIBRATION_FILE = self._latest_water_calib_file(
            board)

        self.PREVIOUS_DATA_FILE = self._previous_data_file()
        self.PREVIOUS_SETTINGS_FILE = self._previous_settings_file()
        self.PREVIOUS_SESSION_PATH = self._previous_session_path()

        if make:
            self.make_missing_folders()

    def make_missing_folders(self):
        self.make_folder(self.IBLRIG_DATA_FOLDER)
        self.make_folder(self.IBLRIG_DATA_SUBJECTS_FOLDER)
        self.make_folder(self.SUBJECT_FOLDER)
        self.make_folder(self.SESSION_DATE_FOLDER)
        self.make_folder(self.SESSION_FOLDER)
        self.make_folder(self.SESSION_RAW_DATA_FOLDER)
        self.make_folder(self.SESSION_RAW_VIDEO_DATA_FOLDER)
        # self.make_folder(self.SESSION_RAW_EPHYS_DATA_FOLDER)
        # self.make_folder(self.SESSION_RAW_IMAGING_DATA_FOLDER)

    def _get_iblrig_commit_hash(self):
        here = os.getcwd()
        os.chdir(self.IBLRIG_FOLDER)
        out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode()
        os.chdir(here)
        return out.strip()

    def _get_iblrig_version_tag(self):
        here = os.getcwd()
        os.chdir(self.IBLRIG_FOLDER)
        tag = subprocess.check_output(["git", "tag",
                                       "--points-at", "HEAD"]).decode().strip()
        os.chdir(here)
        return tag

    def get_bonsai_path(self, use_iblrig_bonsai=True):
        """Checks for Bonsai folder in iblrig.
        Returns string with bonsai executable path."""
        folders = self.get_subfolder_paths(self.IBLRIG_FOLDER)
        bonsai_folder = [x for x in folders if 'Bonsai' in x][0]
        ibl_bonsai = os.path.join(bonsai_folder, 'Bonsai64.exe')

        preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai64.exe"
        if use_iblrig_bonsai is True:
            BONSAI = ibl_bonsai
        elif use_iblrig_bonsai is False and preexisting_bonsai.exists():
            BONSAI = str(preexisting_bonsai)
        elif use_iblrig_bonsai is False and not preexisting_bonsai.exists():
            print("NOT FOUND: {}\n Using packaged Bonsai.".format(
                str(preexisting_bonsai)))
            BONSAI = ibl_bonsai
        return BONSAI

    @staticmethod
    def make_folder(str1):
        """Check if folder path exists and if not create it + parents."""
        path = Path(str1)
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_subfolder_paths(folder):
        out = [os.path.join(folder, x) for x in os.listdir(folder)
               if os.path.isdir(os.path.join(folder, x))]
        return out

    def _iblrig_folder_init(self):
        if '/' in self.IBLRIG_FOLDER:
            p = '{}'.format(os.path.sep).join(self.IBLRIG_FOLDER.split('/'))
        elif '\\' in self.IBLRIG_FOLDER:
            p = '{}'.format(os.path.sep).join(self.IBLRIG_FOLDER.split('\\'))
        return p

    def _iblrig_data_folder_init(self, iblrig_folder, iblrig_data_folder):
        iblrig_folder = Path(iblrig_folder)
        if not iblrig_folder.exists():
            print("\nCouldn't find IBLRIG_FOLDER on file system\n")
            raise IOError

        if iblrig_data_folder is None:
            out = iblrig_folder.parent / 'iblrig_data'
            return str(out)
        else:
            mdf = Path(iblrig_data_folder)
            if mdf.name == 'Subjects':
                out = str(mdf.parent)
            elif mdf.name != 'Subjects':
                out = str(mdf)
            return out

    def _session_number(self):
        if not Path(self.SESSION_DATE_FOLDER).exists():
            return '001'
        session_nums = [int(x) for x in os.listdir(self.SESSION_DATE_FOLDER)
                        if os.path.isdir(os.path.join(self.SESSION_DATE_FOLDER,
                                                      x))]
        if not session_nums:
            out = '00' + str(1)
        elif max(session_nums) < 9:
            out = '00' + str(int(max(session_nums)) + 1)
        elif 99 > max(session_nums) >= 9:
            out = '0' + str(int(max(session_nums)) + 1)
        elif max(session_nums) > 99:
            out = str(int(max(session_nums)) + 1)
        return out

    def _previous_session_folders(self):
        """
        """
        session_folders = []
        if not Path(self.SUBJECT_FOLDER).exists():
            return session_folders

        for date in self.get_subfolder_paths(self.SUBJECT_FOLDER):
            session_folders.extend(self.get_subfolder_paths(date))

        session_folders = [x for x in sorted(session_folders)
                           if self.SESSION_FOLDER not in x]
        return session_folders

    def _previous_data_files(self, typ='data'):

        prev_data_files = []
        prev_session_files = []
        for prev_sess_path in self._previous_session_folders():
            prev_sess_path = os.path.join(prev_sess_path, 'raw_behavior_data')
            if self.BASE_FILENAME + 'Data' in ''.join(os.listdir(
                    prev_sess_path)):
                prev_data_files.extend(os.path.join(prev_sess_path, x) for x
                                       in os.listdir(prev_sess_path) if
                                       self.BASE_FILENAME + 'Data' in x)
                prev_session_files.extend(os.path.join(prev_sess_path, x) for x
                                       in os.listdir(prev_sess_path) if
                                       self.BASE_FILENAME + 'Settings' in x)

        data_out = [x for x in prev_data_files if os.stat(x).st_size != 0]
        settings_out = [
            x for x in prev_session_files if os.stat(x).st_size != 0]

        return data_out if typ == 'data' else settings_out

    def _previous_data_file(self):
        out = sorted(self._previous_data_files())
        if out:
            return out[-1]
        else:
            print('#######################################')
            print('## WARNING:  WILL USE DEFAULT VALUES ##')
            print('#######################################')
            print(' [no previous valid session was found] ')

            return None

    def _previous_settings_file(self):
        out = sorted(self._previous_data_files(typ='settings'))
        if out:
            return out[-1]
        else:
            return None

    def _previous_session_path(self):
        if self.PREVIOUS_DATA_FILE is not None:
            out = str(Path(self.PREVIOUS_DATA_FILE).parent.parent)
        else:
            out = None

        return out

    def _latest_water_calib_file(self, board):
        dsf = Path(self.IBLRIG_DATA_SUBJECTS_FOLDER)
        cal = dsf / '_iblrig_calibration'
        if not cal.exists():
            return None

        if not board:
            return None

        cal_session_folders = []
        for date in self.get_subfolder_paths(str(cal)):
            cal_session_folders.extend(self.get_subfolder_paths(date))

        water_cal_files = []
        for session in cal_session_folders:
            session = Path(session) / 'raw_behavior_data'
            water_cal_files.extend(list(session.glob(
                '_iblrig_calibration_water_function.csv')))

        water_cal_files = sorted(water_cal_files,
                                 key=lambda x: int(x.parent.parent.name))

        if not water_cal_files:
            return

        water_cal_settings = [x.parent / "_iblrig_taskSettings.raw.json"
                              for x in water_cal_files]
        same_board_cal_files = []
        for fcal, s in zip(water_cal_files, water_cal_settings):
            if s.exists():
                with open(str(s), 'r') as f:
                    settings = json.loads(f.readline())
                if settings['PYBPOD_BOARD'] == board:
                    same_board_cal_files.append(fcal)

        same_board_cal_files = sorted(same_board_cal_files,
                                      key=lambda x: int(x.parent.parent.name))
        if same_board_cal_files:
            return str(same_board_cal_files[-1])
        else:
            return


if __name__ == "__main__":
    # spc = SessionPathCreator('C:\\iblrig', None, '_iblrig_test_mouse',
    # 'trainingChoiceWorld')
    spc = SessionPathCreator(
        '/home/nico/Projects/IBL/IBL-github/iblrig',
        '/home/nico/Projects/IBL/IBL-github/iblrig_data',  # /scratch/new',
        '_iblrig_test_mouse', protocol='trainingChoiceWorld', board='box0',
        make=False)

    print(
        "\nIBLRIG_VERSION_TAG", spc.IBLRIG_VERSION_TAG,
        "\nIBLRIG_COMMIT_HASH", spc.IBLRIG_COMMIT_HASH,
        "\nIBLRIG_FOLDER:", spc.IBLRIG_FOLDER,
        "\nIBLRIG_DATA_FOLDER:", spc.IBLRIG_DATA_FOLDER,
        "\nIBLRIG_DATA_SUBJECTS_FOLDER:", spc.IBLRIG_DATA_SUBJECTS_FOLDER,
        "\nSESSION_DATE_FOLDER:", spc.SESSION_DATE_FOLDER,
        "\nSESSION_NUMBER:", spc.SESSION_NUMBER,
        "\nSESSION_DATE:", spc.SESSION_DATE,
        "\nSESSION_FOLDER:", spc.SESSION_FOLDER,
        "\nSESSION_RAW_DATA_FOLDER:", spc.SESSION_RAW_DATA_FOLDER,
        "\nSESSION_DATETIME:", spc.SESSION_DATETIME,
        "\nSESSION_COMPOUND_NAME:", spc.SESSION_COMPOUND_NAME,
        "\nSUBJECT_NAME:", spc.SUBJECT_NAME,
        "\nSUBJECT_FOLDER:", spc.SUBJECT_FOLDER,
        "\nSOUND_STIM_FOLDER:", spc.SOUND_STIM_FOLDER,
        "\nVISUAL_STIM_FOLDER:", spc.VISUAL_STIM_FOLDER,
        "\nVISUAL_STIMULUS_FILE:", spc.VISUAL_STIMULUS_FILE,
        "\nBASE_FILENAME:", spc.BASE_FILENAME,
        "\nSETTINGS_FILE_PATH:", spc.SETTINGS_FILE_PATH,
        "\nDATA_FILE_PATH:", spc.DATA_FILE_PATH,
        "\nLATEST_WATER_CALIBRATION_FILE:", spc.LATEST_WATER_CALIBRATION_FILE,
        "\nPREVIOUS_DATA_FILE:", spc.PREVIOUS_DATA_FILE,
        "\nPREVIOUS_SETTINGS_FILE:", spc.PREVIOUS_SETTINGS_FILE,
        "\nPREVIOUS_SESSION_PATH:", spc.PREVIOUS_SESSION_PATH,
    )
    print('.')
