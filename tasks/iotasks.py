# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, February 5th 2019, 3:13:18 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 5-02-2019 03:13:19.1919
import json
import logging
import shutil
from pathlib import Path
import zipfile
import ibllib.io.raw_data_loaders as raw


import os

log = logging.getLogger('iblrig')


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


def deserialize_pybpod_user_settings(sph_obj):
    sph_obj.PYBPOD_CREATOR = json.loads(sph_obj.PYBPOD_CREATOR)
    sph_obj.PYBPOD_USER_EXTRA = json.loads(sph_obj.PYBPOD_USER_EXTRA)

    sph_obj.PYBPOD_SUBJECTS = [
        json.loads(x.replace("'", '"')) for x in sph_obj.PYBPOD_SUBJECTS]
    if len(sph_obj.PYBPOD_SUBJECTS) == 1:
        sph_obj.PYBPOD_SUBJECTS = sph_obj.PYBPOD_SUBJECTS[0]
    else:
        log.error("Multiple subjects found in PYBPOD_SUBJECTS")
        raise(IOError)

    sph_obj.PYBPOD_SUBJECT_EXTRA = [
        json.loads(x) for x in sph_obj.PYBPOD_SUBJECT_EXTRA[1:-1].split('","')]
    if len(sph_obj.PYBPOD_SUBJECT_EXTRA) == 1:
        sph_obj.PYBPOD_SUBJECT_EXTRA = sph_obj.PYBPOD_SUBJECT_EXTRA[0]

    return sph_obj


def save_session_settings(sph_obj) -> None:
    with open(sph_obj.SETTINGS_FILE_PATH, 'a') as f:
        f.write(json.dumps(sph_obj, cls=ComplexEncoder, indent=1))
        f.write('\n')


def copy_task_code(sph_obj) -> None:
    # Copy behavioral task python code
    src = os.path.join(
        sph_obj.IBLRIG_PARAMS_FOLDER, 'IBL', 'tasks', sph_obj.PYBPOD_PROTOCOL)
    dst = os.path.join(
        sph_obj.SESSION_RAW_DATA_FOLDER, sph_obj.PYBPOD_PROTOCOL)
    shutil.copytree(src, dst)
    # Copy stimulus folder with bonsai workflow
    src = str(Path(
        sph_obj.VISUAL_STIM_FOLDER) / sph_obj.VISUAL_STIMULUS_TYPE)
    dst = str(Path(
        sph_obj.SESSION_RAW_DATA_FOLDER) / sph_obj.VISUAL_STIMULUS_TYPE)
    shutil.copytree(src, dst)
    # Copy video recording folder with bonsai workflow
    src = sph_obj.VIDEO_RECORDING_FOLDER
    dst = os.path.join(
        sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER, 'camera_recordings')
    shutil.copytree(src, dst)


def save_task_code(sph_obj) -> None:
    # zip all existing folders
    # Should be the task code folder and if available stimulus code folder
    behavior_code_files = [
        os.path.join(sph_obj.SESSION_RAW_DATA_FOLDER, x)
        for x in os.listdir(sph_obj.SESSION_RAW_DATA_FOLDER)
        if os.path.isdir(os.path.join(sph_obj.SESSION_RAW_DATA_FOLDER, x))
    ]
    zipit(behavior_code_files, Path(sph_obj.SESSION_RAW_DATA_FOLDER).joinpath(
        '_iblrig_taskCodeFiles.raw.zip')
    )

    video_code_files = [
        os.path.join(sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER, x)
        for x in os.listdir(sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER)
        if os.path.isdir(
            os.path.join(sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER, x))
    ]
    zipit(
        video_code_files, Path(sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER).joinpath(
            '_iblrig_videoCodeFiles.raw.zip')
    )

    [shutil.rmtree(x) for x in behavior_code_files + video_code_files]


def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(
                os.path.join(root, file), os.path.relpath(
                    os.path.join(root, file), os.path.join(path, '..')))


def zipit(dir_list, zip_name):
    zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
    for dir in dir_list:
        zipdir(dir, zipf)
    zipf.close()


def load_data(previous_session_path, i=-1):
    trial_data = raw.load_data(previous_session_path)
    return trial_data[i] if trial_data else None


def load_settings(previous_session_path):
    return raw.load_settings(previous_session_path)
