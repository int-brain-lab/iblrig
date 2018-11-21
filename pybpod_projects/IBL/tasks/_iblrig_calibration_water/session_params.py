# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, November 21st 2018, 4:27:34 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 21-11-2018 04:29:49.4949
import json
import os
import shutil
import zipfile
import types

# from path_helper import SessionPathCreator

from pybpod_projects.IBL.tasks._iblrig_calibration_water.path_helper import SessionPathCreator


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings):
        # =====================================================================
        # IMPORT task_settings, user_settings, and SessionPathCreator params
        # =====================================================================
        if type(task_settings) == types.ModuleType:
            ts = {i: task_settings.__dict__[i]
                for i in [x for x in dir(task_settings) if '__' not in x]}
        elif type(task_settings) == dict:
            ts = task_settings
        self.__dict__.update(ts)
        us = {i: user_settings.__dict__[i]
              for i in [x for x in dir(user_settings) if '__' not in x]}
        self.__dict__.update(us)
        self.deserialize_session_user_settings()

        spc = SessionPathCreator(self.IBLRIG_FOLDER, self.MAIN_DATA_FOLDER,
                                 self.PYBPOD_SUBJECTS[0], self.PYBPOD_PROTOCOL)
        self.__dict__.update(spc.__dict__)
        self.CALIBRATION_FUNCTION_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                                          '_iblrig_calibration_water_function.csv')
        self.CALIBRATION_RANGE_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                                    '_iblrig_calibration_water_range.csv')
        self.CALIBRATION_CURVE_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                                    '_iblrig_calibration_water_curve.pdf')

        # =====================================================================
        # FOLDER STRUCTURE AND DATA FILES
        # =====================================================================
        self._save_session_settings()
        self._save_task_code()

    # =========================================================================
    # METHODS
    # =========================================================================
    # SERIALIZER
    # =========================================================================
    def reprJSON(self):
        d = self.__dict__.copy()
        d['SESSION_DATETIME'] = str(self.SESSION_DATETIME)
        return d

    # =========================================================================
    # PYBPOD USER SETTINGS DESERIALIZATION
    # =========================================================================
    def deserialize_session_user_settings(self):
        self.PYBPOD_CREATOR = json.loads(self.PYBPOD_CREATOR)
        self.PYBPOD_USER_EXTRA = json.loads(self.PYBPOD_USER_EXTRA)

        self.PYBPOD_SUBJECTS = [json.loads(x.replace("'", '"'))
                                for x in self.PYBPOD_SUBJECTS]
        if len(self.PYBPOD_SUBJECTS) == 1:
            self.PYBPOD_SUBJECTS = self.PYBPOD_SUBJECTS[0]
        else:
            print("ERROR: Multiple subjects found in PYBPOD_SUBJECTS")
            raise IOError

        self.PYBPOD_SUBJECT_EXTRA = [json.loads(x) for x in
                                     self.PYBPOD_SUBJECT_EXTRA[1:-1
                                                               ].split('","')]
        if len(self.PYBPOD_SUBJECT_EXTRA) == 1:
            self.PYBPOD_SUBJECT_EXTRA = self.PYBPOD_SUBJECT_EXTRA[0]

    # =========================================================================
    # SERIALIZE AND SAVE
    # =========================================================================
    def _save_session_settings(self):
        with open(self.SETTINGS_FILE_PATH, 'a') as f:
            f.write(json.dumps(self, cls=ComplexEncoder))
            f.write('\n')
        return

    def _save_task_code(self):
        # Copy behavioral task python code
        src = os.path.join(self.IBLRIG_FOLDER, 'pybpod_projects', 'IBL',
                           'tasks', self.PYBPOD_PROTOCOL)
        dst = os.path.join(self.SESSION_RAW_DATA_FOLDER, self.PYBPOD_PROTOCOL)
        shutil.copytree(src, dst)
        # zip all existing folders
        # Should be the task code folder and if available stimulus code folder
        folders_to_zip = [os.path.join(self.SESSION_RAW_DATA_FOLDER, x)
                          for x in os.listdir(self.SESSION_RAW_DATA_FOLDER)
                          if os.path.isdir(os.path.join(
                              self.SESSION_RAW_DATA_FOLDER, x))]
        SessionParamHandler.zipit(
            folders_to_zip, os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                         '_ibl_codeFiles.raw.zip'))

        [shutil.rmtree(x) for x in folders_to_zip]

    @staticmethod
    def zipdir(path, ziph):
        # ziph is zipfile handle
        for root, dirs, files in os.walk(path):
            for file in files:
                ziph.write(os.path.join(root, file),
                           os.path.relpath(os.path.join(root, file),
                                           os.path.join(path, '..')))

    @staticmethod
    def zipit(dir_list, zip_name):
        zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        for dir in dir_list:
            SessionParamHandler.zipdir(dir, zipf)
        zipf.close()
