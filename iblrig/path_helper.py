#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, November 14th 2018, 10:40:43 am
import datetime
import logging
import os
import subprocess
from os import listdir
from os.path import join
from pathlib import Path

from ibllib.io import raw_data_loaders as raw
import platform

import iblrig.logging_  # noqa
import iblrig.params as params

log = logging.getLogger("iblrig")


def get_network_drives():
    if platform.system() == "Linux":
        return "~/Projects/IBL/github/iblserver"
    import win32api
    import win32com.client
    from win32com.shell import shell, shellcon

    NETWORK_SHORTCUTS_FOLDER_PATH = shell.SHGetFolderPath(0, shellcon.CSIDL_NETHOOD, None, 0)
    # Add Logical Drives
    drives = win32api.GetLogicalDriveStrings()
    drives = drives.split("\000")[:-1]
    # Add Network Locations
    network_shortcuts = [
        join(NETWORK_SHORTCUTS_FOLDER_PATH, f) + "\\target.lnk"
        for f in listdir(NETWORK_SHORTCUTS_FOLDER_PATH)
    ]
    shell = win32com.client.Dispatch("WScript.Shell")
    for network_shortcut in network_shortcuts:
        shortcut = shell.CreateShortCut(network_shortcut)
        drives.append(shortcut.Targetpath)

    return drives


def get_iblserver_data_folder(subjects: bool = True):
    drives = get_network_drives()
    if platform.system() == "Linux":
        path = "~/Projects/IBL/github/iblserver"
        return path if not subjects else path + "/Subjects"
    log.debug("Looking for Y:\\ drive")
    drives = [x for x in drives if x == "Y:\\"]
    if len(drives) == 0:
        log.warning(
            "Y:\\ drive not found please map your local server data folder to the Y:\\ drive."
        )
        return None
    elif len(drives) == 1:
        return drives[0] if not subjects else drives[0] + "Subjects"
    else:
        log.warning("Something is not right... ignoring local server configuration.")
        return None


def get_iblrig_folder() -> str:
    import iblrig

    return str(Path(iblrig.__file__).parent.parent)


def get_iblrig_params_folder() -> str:
    iblrig_ = Path(get_iblrig_folder())
    return str(iblrig_.parent / "iblrig_params")


def get_iblrig_data_folder(subjects: bool = True) -> str:
    iblrig_ = Path(get_iblrig_folder())
    out = iblrig_.parent / "iblrig_data"
    sout = iblrig_.parent / "iblrig_data" / "Subjects"
    if not out.exists():
        make_folder(out)
    if not sout.exists():
        make_folder(sout)
    return str(sout) if subjects else str(out)


def get_commit_hash(folder: str):
    here = os.getcwd()
    os.chdir(folder)
    out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    os.chdir(here)
    if not out:
        log.debug("Commit hash is empty string")
    log.debug(f"Found commit hash {out}")
    return out


def get_version_tag(folder: str) -> str:
    here = os.getcwd()
    os.chdir(folder)
    tag = subprocess.check_output(["git", "tag", "--points-at", "HEAD"]).decode().strip()
    os.chdir(here)
    if not tag:
        log.debug(f"NOT FOUND: Version TAG for {folder}")
    log.debug(f"Found version tag {tag}")
    return tag


def get_session_next_number(session_date_folder: str) -> str:
    log.debug("Initializing session number")
    if not Path(session_date_folder).exists():
        return "001"
    session_nums = [
        int(x)
        for x in os.listdir(session_date_folder)
        if os.path.isdir(os.path.join(session_date_folder, x))
    ]
    if not session_nums:
        out = "00" + str(1)
    elif max(session_nums) < 9:
        out = "00" + str(int(max(session_nums)) + 1)
    elif 99 > max(session_nums) >= 9:
        out = "0" + str(int(max(session_nums)) + 1)
    elif max(session_nums) > 99:
        out = str(int(max(session_nums)) + 1)
    log.debug(f"Setting session number to: {out}")

    return out


def get_visual_stim_folder_name(protocol: str) -> str:
    if "habituation" in protocol or "sync_test" in protocol:
        return "GaborHabituationTask"
    elif "ephys_certification" in protocol:
        return "ephys_certification"
    else:
        return "GaborIBLTask"


def get_water_calibration_func_file(latest: bool = True) -> Path or list:
    data_folder = Path(get_iblrig_data_folder())
    func_files = sorted(data_folder.rglob("_iblrig_calibration_water_function.csv"))
    if not func_files:
        return Path()
    return func_files[-1] if latest else func_files


def get_water_calibration_range_file(latest=True) -> Path or list:
    data_folder = Path(get_iblrig_data_folder())
    range_files = sorted(data_folder.rglob("_iblrig_calibration_water_range.csv"))
    if not range_files:
        return Path()
    return range_files[-1] if latest else range_files


def load_water_calibraition_func_file(fpath: str or Path) -> dict:
    if not Path(fpath).exists():
        return

    import pandas as pd

    # TODO: remove pandas dependency
    df1 = pd.read_csv(fpath)
    if df1.empty:
        return {
            "WATER_CALIBRATION_OPEN_TIMES": None,
            "WATER_CALIBRATION_WEIGHT_PERDROP": None,
        }

    return {
        "WATER_CALIBRATION_OPEN_TIMES": df1["open_time"].to_list(),
        "WATER_CALIBRATION_WEIGHT_PERDROP": df1["weight_perdrop"].to_list(),
    }


def load_water_calibraition_range_file(fpath: str or Path) -> dict:
    if not Path(fpath).exists():
        return

    import pandas as pd

    # TODO: remove pandas dependency
    df1 = pd.read_csv(fpath)
    if df1.empty:
        return {"WATER_CALIBRATION_RANGE": [None, None]}

    return {
        "WATER_CALIBRATION_RANGE": [
            df1.min_open_time.iloc[0],
            df1.max_open_time.iloc[0],
        ]
    }


def make_folder(str1: str or Path) -> None:
    """Check if folder path exists and if not create it + parents."""
    path = Path(str1)
    path.mkdir(parents=True, exist_ok=True)
    log.debug(f"Created folder {path}")


def get_previous_session_folders(subject_name: str, session_folder: str) -> list:
    """"""
    log.debug("Looking for previous session folders")
    subject_folder = Path(get_iblrig_data_folder(subjects=True)) / subject_name
    sess_folders = []
    if not subject_folder.exists():
        log.debug(f"NOT FOUND: No previous sessions for subject {subject_folder.name}")
        return sess_folders

    for date in get_subfolder_paths(subject_folder):
        sess_folders.extend(get_subfolder_paths(date))

    sess_folders = [x for x in sorted(sess_folders) if session_folder not in x]
    if not sess_folders:
        log.debug(f"NOT FOUND: No previous sessions for subject {subject_folder.name}")

    log.debug(f"Found {len(sess_folders)} session folders for mouse {subject_folder.name}")

    return sess_folders


def get_previous_data_files(
    protocol: str, subject_name: str, session_folder: str, typ: str = "data"
) -> list:
    log.debug(f"Looking for previous files of type: {typ}")
    prev_data_files = []
    prev_session_files = []
    data_fname = "_iblrig_taskData.raw.jsonable"
    settings_fname = "_iblrig_taskSettings.raw.json"
    log.debug(f"Looking for files:{data_fname} AND {settings_fname}")
    for prev_sess_path in get_previous_session_folders(subject_name, session_folder):
        prev_sess_path = Path(prev_sess_path) / "raw_behavior_data"
        # Get all data and settings file if they both exist
        if (prev_sess_path / data_fname).exists() and (prev_sess_path / settings_fname).exists():
            prev_data_files.append(prev_sess_path / data_fname)
            prev_session_files.append(prev_sess_path / settings_fname)
    log.debug(f"Found {len(prev_data_files)} file pairs")
    # Remove empty files
    ds_out = [
        (d, s)
        for d, s in zip(prev_data_files, prev_session_files)
        if d.stat().st_size != 0 and s.stat().st_size != 0
    ]
    log.debug(f"Found {len(ds_out)} non empty file pairs")
    # Remove sessions of different task protocols
    ds_out = [
        (d, s)
        for d, s in ds_out
        if protocol in raw.load_settings(str(s.parent.parent))["PYBPOD_PROTOCOL"]
    ]
    log.debug(f"Found {len(ds_out)} file pairs for protocol {protocol}")
    data_out = [str(d) for d, s in ds_out]
    settings_out = [str(s) for d, s in ds_out]
    if not data_out:
        log.debug(f"NOT FOUND: Previous data files for task {protocol}")
    if not settings_out:
        log.debug(f"NOT FOUND: Previous settings files for task {protocol}")
    log.debug(f"Reurning {typ} files")

    return data_out if typ == "data" else settings_out


def get_previous_data_file(protocol: str, subject_name: str, session_folder: str):
    log.debug("Getting previous data file")
    out = sorted(get_previous_data_files(protocol, subject_name, session_folder))
    if out:
        log.debug(f"Previous data file: {out[-1]}")
        return out[-1]
    else:
        log.debug("NOT FOUND: Previous data file")
        return None


def get_previous_settings_file(protocol: str, subject_name: str, session_folder: str):
    log.debug("Getting previous settings file")
    out = sorted(get_previous_data_files(protocol, subject_name, session_folder, typ="settings"))
    if out:
        log.debug(f"Previous settings file: {out[-1]}")
        return out[-1]
    else:
        log.debug("NOT FOUND: Previous settings file")
        return None


def get_previous_session_path(protocol: str, subject_name: str, session_folder: str):
    log.debug("Getting previous session path")
    previous_data_file = get_previous_data_file(protocol, subject_name, session_folder)
    if previous_data_file is not None:
        out = str(Path(previous_data_file).parent.parent)
        log.debug(f"Previous session path: {out}")
    else:
        out = None
        log.debug("NOT FOUND: Previous session path")

    return out


def get_subfolder_paths(folder: str) -> str:
    out = [
        os.path.join(folder, x)
        for x in os.listdir(folder)
        if os.path.isdir(os.path.join(folder, x))
    ]
    log.debug(f"Found {len(out)} subfolders for folder {folder}")

    return out


def get_bonsai_path(use_iblrig_bonsai: bool = True) -> str:
    """Checks for Bonsai folder in iblrig.
    Returns string with bonsai executable path."""
    iblrig_folder = get_iblrig_folder()
    folders = get_subfolder_paths(iblrig_folder)
    bonsai_folder = [x for x in folders if "Bonsai" in x][0]
    ibl_bonsai = os.path.join(bonsai_folder, "Bonsai64.exe")
    if not Path(ibl_bonsai).exists():  # if Bonsai64 does not exist Bonsai v >2.5.0
        ibl_bonsai = os.path.join(bonsai_folder, "Bonsai.exe")

    preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai64.exe"
    if not preexisting_bonsai.exists():
        preexisting_bonsai = Path.home() / "AppData/Local/Bonsai/Bonsai.exe"

    if use_iblrig_bonsai is True:
        BONSAI = ibl_bonsai
    elif use_iblrig_bonsai is False and preexisting_bonsai.exists():
        BONSAI = str(preexisting_bonsai)
    elif use_iblrig_bonsai is False and not preexisting_bonsai.exists():
        log.debug(f"NOT FOUND: {preexisting_bonsai}. Using packaged Bonsai")
        BONSAI = ibl_bonsai
    log.debug(f"Found Bonsai executable: {BONSAI}")

    return BONSAI


def get_visual_stim_type(protocol: str) -> str:
    if "bpod_ttl_test" in protocol:
        return "GaborTestStimuli"
    elif "ephys_certification" in protocol:
        return "ephys_certification"
    else:
        return "GaborIBLTask"


def get_visual_stim_file_name(visual_stimulus_type: str) -> str:
    if "GaborTestStimuli" in visual_stimulus_type:
        return "Gabor2D_TTLTest.bonsai"
    elif "ephys_certification" in visual_stimulus_type:
        return "ephys_certification.bonsai"
    elif "GaborIBLTask" in visual_stimulus_type:
        return "Gabor2D.bonsai"
    elif "passiveChoiceWorld" in visual_stimulus_type:  # Never called?
        return "passiveChoiceWorld_passive.bonsai"


def get_session_number(session_date_folder: str) -> str:
    log.debug("Initializing session number")
    if not Path(session_date_folder).exists():
        return "001"
    session_nums = [
        int(x)
        for x in os.listdir(session_date_folder)
        if os.path.isdir(os.path.join(session_date_folder, x))
    ]
    if not session_nums:
        out = "00" + str(1)
    elif max(session_nums) < 9:
        out = "00" + str(int(max(session_nums)) + 1)
    elif 99 > max(session_nums) >= 9:
        out = "0" + str(int(max(session_nums)) + 1)
    elif max(session_nums) > 99:
        out = str(int(max(session_nums)) + 1)
    log.debug(f"Setting session number to: {out}")

    return out


def get_pregen_session_folder() -> str:
    iblrig_path = Path(get_iblrig_folder())
    return str(iblrig_path / "tasks" / "_iblrig_tasks_ephysChoiceWorld" / "sessions")


class SessionPathCreator(object):
    # add subject name and protocol (maybe have a metadata struct)
    def __init__(self, subject_name, protocol=False, make=False):

        self.IBLRIG_FOLDER = get_iblrig_folder()
        self.IBLRIG_EPHYS_SESSION_FOLDER = get_pregen_session_folder()
        self._BOARD = params.get_board_name()

        self._PROTOCOL = protocol

        self.IBLRIG_COMMIT_HASH = get_commit_hash(self.IBLRIG_FOLDER)
        self.IBLRIG_VERSION_TAG = get_version_tag(self.IBLRIG_FOLDER)
        self.IBLRIG_PARAMS_FOLDER = get_iblrig_params_folder()
        self.IBLRIG_DATA_FOLDER = get_iblrig_data_folder(subjects=False)
        self.IBLRIG_DATA_SUBJECTS_FOLDER = get_iblrig_data_folder(subjects=True)

        self.PARAMS = params.load_params_file()
        # TODO: check if can remove old bpod_comports file
        self.IBLRIG_PARAMS_FILE = str(Path(self.IBLRIG_PARAMS_FOLDER) / ".bpod_comports.json")
        self.SUBJECT_NAME = subject_name
        self.SUBJECT_FOLDER = os.path.join(self.IBLRIG_DATA_SUBJECTS_FOLDER, self.SUBJECT_NAME)

        self.BONSAI = get_bonsai_path(use_iblrig_bonsai=True)
        self.VISUAL_STIM_FOLDER = str(Path(self.IBLRIG_FOLDER) / "visual_stim")
        self.VISUAL_STIMULUS_TYPE = get_visual_stim_type(self._PROTOCOL)
        self.VISUAL_STIMULUS_FILE_NAME = get_visual_stim_file_name(self.VISUAL_STIMULUS_TYPE)
        self.VISUAL_STIMULUS_FILE = str(
            Path(self.VISUAL_STIM_FOLDER)
            / self.VISUAL_STIMULUS_TYPE
            / self.VISUAL_STIMULUS_FILE_NAME
        )

        self.VIDEO_RECORDING_FOLDER = os.path.join(
            self.IBLRIG_FOLDER, "devices", "camera_recordings"
        )
        self.VIDEO_RECORDING_FILE = os.path.join(
            self.VIDEO_RECORDING_FOLDER, "TrainingRig_SaveVideo_TrainingTasks.bonsai"
        )

        self.MIC_RECORDING_FOLDER = os.path.join(self.IBLRIG_FOLDER, "devices", "microphone")
        self.MIC_RECORDING_FILE = os.path.join(self.MIC_RECORDING_FOLDER, "record_mic.bonsai")

        self.SESSION_DATETIME = datetime.datetime.now().isoformat()
        self.SESSION_DATE = datetime.datetime.now().date().isoformat()

        self.SESSION_DATE_FOLDER = os.path.join(self.SUBJECT_FOLDER, self.SESSION_DATE)

        self.SESSION_NUMBER = get_session_number(self.SESSION_DATE_FOLDER)

        self.SESSION_FOLDER = str(Path(self.SESSION_DATE_FOLDER) / self.SESSION_NUMBER)
        self.SESSION_RAW_DATA_FOLDER = os.path.join(self.SESSION_FOLDER, "raw_behavior_data")
        self.SESSION_RAW_VIDEO_DATA_FOLDER = os.path.join(self.SESSION_FOLDER, "raw_video_data")
        self.SESSION_RAW_EPHYS_DATA_FOLDER = os.path.join(self.SESSION_FOLDER, "raw_ephys_data")
        self.SESSION_RAW_IMAGING_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, "raw_imaging_data"
        )
        self.SESSION_RAW_PASSIVE_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, "raw_passive_data"
        )

        self.SESSION_NAME = "{}".format(os.path.sep).join(
            [self.SUBJECT_NAME, self.SESSION_DATE, self.SESSION_NUMBER]
        )

        self.BASE_FILENAME = "_iblrig_task"
        self.SETTINGS_FILE_PATH = os.path.join(
            self.SESSION_RAW_DATA_FOLDER, self.BASE_FILENAME + "Settings.raw.json"
        )
        self.DATA_FILE_PATH = os.path.join(
            self.SESSION_RAW_DATA_FOLDER, self.BASE_FILENAME + "Data.raw.jsonable"
        )
        # Water calinbration files
        self.LATEST_WATER_CALIBRATION_FILE = get_water_calibration_func_file(latest=True)
        self.LATEST_WATER_CALIB_RANGE_FILE = get_water_calibration_range_file(latest=True)
        if self.LATEST_WATER_CALIBRATION_FILE.parent != self.LATEST_WATER_CALIB_RANGE_FILE.parent:
            self.LATEST_WATER_CALIBRATION_FILE = str(self.LATEST_WATER_CALIBRATION_FILE)
            self.LATEST_WATER_CALIB_RANGE_FILE = None
        else:
            self.LATEST_WATER_CALIBRATION_FILE = str(self.LATEST_WATER_CALIBRATION_FILE)
            self.LATEST_WATER_CALIB_RANGE_FILE = str(self.LATEST_WATER_CALIB_RANGE_FILE)
        if str(self.LATEST_WATER_CALIBRATION_FILE) == ".":
            self.LATEST_WATER_CALIBRATION_FILE = None
            self.LATEST_WATER_CALIB_RANGE_FILE = None
        # Previous session files
        self.PREVIOUS_DATA_FILE = get_previous_data_file(
            self._PROTOCOL, self.SUBJECT_NAME, self.SESSION_FOLDER
        )
        self.PREVIOUS_SETTINGS_FILE = get_previous_settings_file(
            self._PROTOCOL, self.SUBJECT_NAME, self.SESSION_FOLDER
        )
        self.PREVIOUS_SESSION_PATH = get_previous_session_path(
            self._PROTOCOL, self.SUBJECT_NAME, self.SESSION_FOLDER
        )

        if make:
            self.make_missing_folders(make)
        self.display_logs()

    def make_missing_folders(self, makelist):
        """
        makelist = True will make default folders with only raw_behavior_data
        makelist = False will not make any folders
        makelist = [list] will make the default folders and the raw_folders
        that are specifiec in the list
        """
        if isinstance(makelist, bool) and makelist is True:
            log.debug("Making default folders")
            make_folder(self.IBLRIG_DATA_FOLDER)
            make_folder(self.IBLRIG_DATA_SUBJECTS_FOLDER)
            make_folder(self.SUBJECT_FOLDER)
            make_folder(self.SESSION_DATE_FOLDER)
            make_folder(self.SESSION_FOLDER)
            make_folder(self.SESSION_RAW_DATA_FOLDER)
        elif isinstance(makelist, list):
            log.debug(f"Making extra folders for {makelist}")
            self.make_missing_folders(True)
            if "video" in makelist:
                make_folder(self.SESSION_RAW_VIDEO_DATA_FOLDER)
            if "ephys" in makelist:
                make_folder(self.SESSION_RAW_EPHYS_DATA_FOLDER)
            if "imag" in makelist:
                make_folder(self.SESSION_RAW_IMAGING_DATA_FOLDER)
            if "passive" in makelist:
                make_folder(self.SESSION_RAW_PASSIVE_DATA_FOLDER)

        return

    def display_logs(self):
        # User info and warnings
        for k in self.__dict__:
            if not self.__dict__[k]:
                log.info(f"NOT FOUND: {k}")
                if k == "IBLRIG_VERSION_TAG":
                    msg = """
        ##########################################
            NOT FOUND: IBLRIG_VERSION_TAG
        ##########################################
        You appear to be on an uncommitted version
        of iblrig. Please run iblrig/update.py to
        check which is the latest version.
        ##########################################"""
                    log.warning(msg)

                if k == "PREVIOUS_DATA_FILE" and "training" in self._PROTOCOL:
                    msg = """
        ##########################################
            NOT FOUND: PREVIOUS_DATA_FILE
        ##########################################
                    USING INIT VALUES
        ##########################################"""
                    log.warning(msg)
                if k == "LATEST_WATER_CALIBRATION_FILE":
                    msg = """
        ##########################################
         NOT FOUND: LATEST_WATER_CALIBRATION_FILE
        ##########################################"""
                    log.warning(msg)
                if k == "LATEST_WATER_CALIB_RANGE_FILE":
                    msg = """
        ##########################################
         NOT FOUND: LATEST_WATER_CALIB_RANGE_FILE
        ##########################################
                    Using full range
        ##########################################
        """
                    log.warning(msg)


if __name__ == "__main__":
    # spc = SessionPathCreator('C:\\iblrig', None, '_iblrig_test_mouse',
    # 'trainingChoiceWorld')
    # '/coder/mnt/nbonacchi/iblrig', None,
    spc = SessionPathCreator("_iblrig_test_mouse", protocol="passiveChoiceWorld", make=True)

    print("")
    for k in spc.__dict__:
        print(f"{k}: {spc.__dict__[k]}")

    print(".")
