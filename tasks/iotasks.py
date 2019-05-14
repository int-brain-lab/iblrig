#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, February 5th 2019, 3:13:18 pm
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

import numpy as np

import ibllib.io.raw_data_loaders as raw
from ibllib.graphic import numinput
import misc

log = logging.getLogger('iblrig')


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


def deserialize_pybpod_user_settings(sph: object) -> object:
    sph.PYBPOD_CREATOR = json.loads(sph.PYBPOD_CREATOR)
    sph.PYBPOD_USER_EXTRA = json.loads(sph.PYBPOD_USER_EXTRA)

    sph.PYBPOD_SUBJECTS = [
        json.loads(x.replace("'", '"')) for x in sph.PYBPOD_SUBJECTS]
    if len(sph.PYBPOD_SUBJECTS) == 1:
        sph.PYBPOD_SUBJECTS = sph.PYBPOD_SUBJECTS[0]
    else:
        log.error("Multiple subjects found in PYBPOD_SUBJECTS")
        raise(IOError)

    sph.PYBPOD_SUBJECT_EXTRA = [
        json.loads(x) for x in sph.PYBPOD_SUBJECT_EXTRA[1:-1].split('","')]
    if len(sph.PYBPOD_SUBJECT_EXTRA) == 1:
        sph.PYBPOD_SUBJECT_EXTRA = sph.PYBPOD_SUBJECT_EXTRA[0]

    return sph


def save_session_settings(sph: object) -> None:
    with open(sph.SETTINGS_FILE_PATH, 'a') as f:
        f.write(json.dumps(sph, cls=ComplexEncoder, indent=1))
        f.write('\n')


def copy_task_code(sph: object) -> None:
    # Copy behavioral task python code
    src = os.path.join(
        sph.IBLRIG_PARAMS_FOLDER, 'IBL', 'tasks', sph.PYBPOD_PROTOCOL)
    dst = os.path.join(
        sph.SESSION_RAW_DATA_FOLDER, sph.PYBPOD_PROTOCOL)
    shutil.copytree(src, dst)
    # Copy stimulus folder with bonsai workflow
    src = str(Path(
        sph.VISUAL_STIM_FOLDER) / sph.VISUAL_STIMULUS_TYPE)
    dst = str(Path(
        sph.SESSION_RAW_DATA_FOLDER) / sph.VISUAL_STIMULUS_TYPE)
    shutil.copytree(src, dst)


def copy_video_code(sph: object) -> None:
    # Copy video recording folder with bonsai workflow
    src = sph.VIDEO_RECORDING_FOLDER
    dst = os.path.join(
        sph.SESSION_RAW_VIDEO_DATA_FOLDER, 'camera_recordings')
    shutil.copytree(src, dst)


def save_task_code(sph: object) -> None:
    # zip all existing folders
    # Should be the task code folder and if available stimulus code folder
    behavior_code_files = [
        os.path.join(sph.SESSION_RAW_DATA_FOLDER, x)
        for x in os.listdir(sph.SESSION_RAW_DATA_FOLDER)
        if os.path.isdir(os.path.join(sph.SESSION_RAW_DATA_FOLDER, x))
    ]
    zipit(behavior_code_files, Path(sph.SESSION_RAW_DATA_FOLDER).joinpath(
        '_iblrig_taskCodeFiles.raw.zip')
    )

    [shutil.rmtree(x) for x in behavior_code_files]


def save_video_code(sph: object) -> None:
    # zip all existing folders
    # Should be the task code folder and if available stimulus code folder
    video_code_files = [
        os.path.join(sph.SESSION_RAW_VIDEO_DATA_FOLDER, x)
        for x in os.listdir(sph.SESSION_RAW_VIDEO_DATA_FOLDER)
        if os.path.isdir(
            os.path.join(sph.SESSION_RAW_VIDEO_DATA_FOLDER, x))
    ]
    zipit(
        video_code_files, Path(sph.SESSION_RAW_VIDEO_DATA_FOLDER).joinpath(
            '_iblrig_videoCodeFiles.raw.zip')
    )

    [shutil.rmtree(x) for x in video_code_files]


def zipdir(path: str, ziph: zipfile.ZipFile) -> None:
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(
                os.path.join(root, file), os.path.relpath(
                    os.path.join(root, file), os.path.join(path, '..')))


def zipit(dir_list: list, zip_name: str) -> None:
    zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
    for dir in dir_list:
        zipdir(dir, zipf)
    zipf.close()


def load_data(previous_session_path: str, i: int = -1) -> dict:
    trial_data = raw.load_data(previous_session_path)
    return trial_data[i] if trial_data else None


def load_settings(previous_session_path: str) -> dict:
    return raw.load_settings(previous_session_path)


def load_session_order_and_idx(sph: object) -> object:
    if ((not sph.LAST_SETTINGS_DATA) or
            ('SESSION_ORDER' not in sph.LAST_SETTINGS_DATA.keys())):
        sph.SESSION_ORDER = misc.draw_session_order()
        sph.SESSION_IDX = 0
    elif 'SESSION_ORDER' in sph.LAST_SETTINGS_DATA.keys():
        sph.SESSION_ORDER = sph.LAST_SETTINGS_DATA['SESSION_ORDER']
        sph.SESSION_IDX = sph.LAST_SETTINGS_DATA['SESSION_IDX'] + 1
    # Confirm this is the session to load. If not override SESSION_IDX
    ses_num = int(sph.SESSION_IDX + 1)
    ses_num = numinput(
        "Confirm session to load", "Load recording session number",
        default=ses_num, askint=True, minval=1, maxval=12)
    if ses_num != sph.SESSION_IDX + 1:
        sph.SESSION_IDX = ses_num - 1
    return sph


def load_session_pcqs(sph: object) -> object:
    num = sph.SESSION_ORDER[sph.SESSION_IDX]
    base = sph.IBLRIG_EPHYS_SESSION_FOLDER
    sph.SESSION_LOADED_FILE_PATH = str(Path(base) / f'pcqs_session_{num}.npy')
    pcqs = np.load(Path(sph.SESSION_LOADED_FILE_PATH))
    len_block = np.load(Path(base) / f'pcqs_session_{num}_len_blocks.npy')

    sph.POSITIONS = pcqs[:, 0].tolist()
    sph.CONTRASTS = pcqs[:, 1].tolist()
    sph.QUIESCENT_PERIOD = pcqs[:, 2].tolist()
    sph.STIM_PHASE = pcqs[:, 3].tolist()
    sph.LEN_BLOCKS = len_block.tolist()

    return sph
