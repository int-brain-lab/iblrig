# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, November 14th 2018, 10:40:43 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 14-11-2018 10:41:08.088
import datetime
import os
from pathlib import Path
from sys import platform

from dateutil import parser


class SessionPathCreator(object):
    def __init__(self, iblrig_folder, main_data_folder, subject_name, 
                 protocol, make_folders=True):  # add subject name and protocol (maybe have a metadata struct)
        if platform == 'linux':
            self.IBLRIG_FOLDER = '/home/nico/Projects/IBL/IBL-github/iblrig'
        else:
            self.IBLRIG_FOLDER = str(Path(iblrig_folder))
        self.IBLRIG_PARAMS_FOLDER = str(Path(self.IBLRIG_FOLDER).parent / 'iblrig_params')
        self.ROOT_DATA_FOLDER = self._root_data_folder(self.IBLRIG_FOLDER,
                                                       main_data_folder)
        self.SOUND_STIM_FOLDER = os.path.join(self.IBLRIG_FOLDER, 'sound_stim',
                                              'sounds')
        self.VISUAL_STIM_FOLDER = os.path.join(self.IBLRIG_FOLDER,
                                               'visual_stim', 'Gabor2D')
        self.VIDEO_RECORDING_FOLDER = os.path.join(self.IBLRIG_FOLDER,
                                               'visual_stim',
                                               'camera_recordings')
        self.VISUAL_STIMULUS_FILE = os.path.join(self.IBLRIG_FOLDER,
                                                 'visual_stim', 'Gabor2D',
                                                 'Gabor2D.bonsai')
        self.VIDEO_RECORDING_FILE = os.path.join(self.IBLRIG_FOLDER,
                                                 'visual_stim',
                                                 'camera_recordings',
                                                 'one_camera.bonsai')
        self.SUBJECT_NAME = subject_name
        self.SUBJECT_FOLDER = self.check_folder(self.ROOT_DATA_FOLDER,
                                                self.SUBJECT_NAME)
        self.SESSION_DATETIME = datetime.datetime.now()
        self.SESSION_DATE = self.SESSION_DATETIME.date().isoformat()
        self.SESSION_DATE_FOLDER = self.check_folder(self.SUBJECT_FOLDER,
                                                     self.SESSION_DATE)
        self.SESSION_NUMBER = self._session_number()
        self.SESSION_FOLDER = self.check_folder(self.SESSION_DATE_FOLDER,
                                                self.SESSION_NUMBER)
        self.SESSION_RAW_DATA_FOLDER = self.check_folder(self.SESSION_FOLDER,
                                                         'raw_behavior_data')
        self.SESSION_RAW_VIDEO_DATA_FOLDER = self.check_folder(self.SESSION_FOLDER,
                                                               'raw_video_data')
        self.SESSION_RAW_EPHYS_DATA_FOLDER = self.check_folder(self.SESSION_FOLDER,
                                                               'raw_video_data')
        self.SESSION_RAW_IMAGING_DATA_FOLDER = self.check_folder(self.SESSION_FOLDER,
                                                               'raw_video_data')
        self.SESSION_NAME = '{}'.format(os.path.sep).join([self.SUBJECT_NAME,
                                                           self.SESSION_DATE,
                                                           self.SESSION_NUMBER,
                                                           protocol,
                                                           ])
        self.BASE_FILENAME = '_iblrig_task'
        self.SETTINGS_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                               self.BASE_FILENAME +
                                               'Settings.raw.json')
        self.DATA_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                           self.BASE_FILENAME +
                                           'Data.raw.jsonable')

        self.LATEST_WATER_CALIBRATION_FILE = self._latest_water_calibration_file()
        self.PREVIOUS_DATA_FILE = self._previous_data_file()

    def _root_data_folder(self, iblrig_folder, main_data_folder):
        iblrig_folder = Path(iblrig_folder)
        if main_data_folder is None:
            try:
                iblrig_folder.exists()
                out = iblrig_folder.parent / 'iblrig_data' / 'Subjects'
                out.mkdir(parents=True, exist_ok=True)
                return str(out)
            except IOError as e:
                print(e, "\nCouldn't find IBLRIG_FOLDER in file system\n")
        else:
            return main_data_folder

    def get_bonsai_path(self, use_iblrig_bonsai=True):
        """Checks for Bonsai folder in iblrig.
        Returns string with bonsai executable path."""
        folders = self.get_subfolder_paths(self.IBLRIG_FOLDER)
        bonsai_folder = [x for x in folders if 'Bonsai' in x][0]
        ibl_bonsai = os.path.join(bonsai_folder, 'Bonsai64.exe')

        preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai64.exe"
        if use_iblrig_bonsai == True:
            BONSAI = ibl_bonsai
        elif use_iblrig_bonsai == False and preexisting_bonsai.exists():
            BONSAI = str(preexisting_bonsai)
        elif use_iblrig_bonsai == False and not preexisting_bonsai.exists():
            print("NOT FOUND: {}\n Using packaged Bonsai.".format(
                str(preexisting_bonsai)))
            BONSAI = ibl_bonsai
        return BONSAI

    @staticmethod
    def check_folder(str1, str2=None):
        """Check if folder path exists and if not create it."""
        if str2 is not None:
            f = os.path.join(str1, str2)
        else:
            f = str1
        if not os.path.exists(f):
            os.mkdir(f)
        return f

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

    def _root_data_folder(self, iblrig_folder, main_data_folder):
        iblrig_folder = Path(iblrig_folder)
        if main_data_folder is None:
            try:
                iblrig_folder.exists()
                out = iblrig_folder.parent / 'iblrig_data' / 'Subjects'
                out.mkdir(parents=True, exist_ok=True)
                return str(out)
            except IOError as e:
                print(e, "\nCouldn't find IBLRIG_FOLDER in file system\n")
        else:
            return main_data_folder

    def _session_number(self):
        session_nums = [int(x) for x in os.listdir(self.SESSION_DATE_FOLDER)
                        if os.path.isdir(os.path.join(self.SESSION_DATE_FOLDER,
                                                      x))]
        if not session_nums:
            out = str(1)
        else:
            out = str(int(max(session_nums)) + 1)

        return out

    def _previous_session_folders(self):
        """
        """
        session_folders = []
        for date in self.get_subfolder_paths(self.SUBJECT_FOLDER):
            session_folders.extend(self.get_subfolder_paths(date))

        session_folders = [x for x in sorted(session_folders)
                           if self.SESSION_FOLDER not in x]
        return session_folders

    def _previous_data_files(self):
        prev_data_files = []
        for prev_sess_path in self._previous_session_folders():
            prev_sess_path = os.path.join(prev_sess_path, 'raw_behavior_data')
            if self.BASE_FILENAME + 'Data' in ''.join(os.listdir(
                    prev_sess_path)):
                prev_data_files.extend(os.path.join(prev_sess_path, x) for x
                                       in os.listdir(prev_sess_path) if
                                       self.BASE_FILENAME + 'Data' in x)

        return prev_data_files

    def _previous_data_file(self):
        out = sorted(self._previous_data_files())
        if out:
            return out[-1]
        else:
            return None

    def _latest_water_calibration_file(self):
        rdf = Path(self.ROOT_DATA_FOLDER)
        cal = rdf / '_iblrig_calibration'
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
        
        return str(sorted(water_cal_files)[-1])

       
if __name__ == "__main__":
    spc = SessionPathCreator('C:\\iblrig', None, '_iblrig_test_mouse', 'trainingChoiceWorld')
    print("\nBASE_FILENAME:", spc.BASE_FILENAME,
          "\nPREVIOUS_DATA_FILE:", spc.PREVIOUS_DATA_FILE,
          "\nSESSION_DATETIME:", spc.SESSION_DATETIME,
          "\nSESSION_NAME:", spc.SESSION_NAME,
          "\nSETTINGS_FILE_PATH:", spc.SETTINGS_FILE_PATH,
          "\nSUBJECT_NAME:", spc.SUBJECT_NAME,
          "\nDATA_FILE_PATH:", spc.DATA_FILE_PATH,
          "\nROOT_DATA_FOLDER:", spc.ROOT_DATA_FOLDER,
          "\nSESSION_DATE_FOLDER:", spc.SESSION_DATE_FOLDER,
          "\nSESSION_NUMBER:", spc.SESSION_NUMBER,
          "\nSOUND_STIM_FOLDER:", spc.SOUND_STIM_FOLDER,
          "\nVISUAL_STIMULUS_FILE:", spc.VISUAL_STIMULUS_FILE,
          "\nIBLRIG_FOLDER:", spc.IBLRIG_FOLDER,
          "\nSESSION_DATE:", spc.SESSION_DATE,
          "\nSESSION_FOLDER:", spc.SESSION_FOLDER,
          "\nSESSION_RAW_DATA_FOLDER:", spc.SESSION_RAW_DATA_FOLDER,
          "\nSUBJECT_FOLDER:", spc.SUBJECT_FOLDER,
          "\nVISUAL_STIM_FOLDER:", spc.VISUAL_STIM_FOLDER,
          "\LATEST_WATER_CALIBRATION_FILE:", spc.LATEST_WATER_CALIBRATION_FILE)
    print('.')
