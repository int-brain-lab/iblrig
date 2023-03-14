"""
Various get functions to return paths of folders and network drives
"""
import datetime
import json
import logging
import os
from pathlib import Path
import subprocess

import yaml
from iblutil.util import Bunch

import iblrig
from iblrig import params as pybpod_params

log = logging.getLogger("iblrig")


def load_settings_yaml(file_name):
    with open(Path(iblrig.__file__).parents[1].joinpath('settings', file_name)) as fp:
        rs = yaml.safe_load(fp)
    return Bunch(rs)


IBLRIG_SETTINGS = load_settings_yaml('iblrig_settings.yaml')


def get_remote_server_path(params=None, subjects: bool = True) -> Path or None:
    """
    Get the iblrig server path configured in the settings/iblrig_params.yaml file
    If none is found returns ~/iblrig_data/server
    """
    data_path = IBLRIG_SETTINGS.get("iblrig_local_server_path")
    data_path = data_path or Path.home().joinpath("iblrig_data", "remote_server")
    # Return the "Subjects" subdirectory by default
    return Path(data_path) / "Subjects" if subjects else data_path


def get_iblrig_local_data_path(subjects: bool = True) -> Path or None:
    """
    Get the iblrig_local_data_path configured in the settings/iblrig_params.yaml file
    If none is found returns ~/iblrig_data/local
    """
    data_path = IBLRIG_SETTINGS.get("iblrig_local_data_path")
    data_path = data_path or Path.home().joinpath("iblrig_data", "local")
    # Return the "Subjects" subdirectory by default
    return Path(data_path) / "Subjects" if subjects else Path(data_path)


def get_iblrig_remote_server_data_path(subjects: bool = True) -> Path or None:
    """
    Get the remote_server_data configured in the settings/iblrig_params.yaml file
    If none is found returns ~/iblrig_data/remote
    """
    data_path = IBLRIG_SETTINGS.get("iblrig_local_data_path")
    data_path = data_path or Path.home().joinpath("iblrig_data", "remote_data")
    # Return the "Subjects" subdirectory by default
    return Path(data_path) / "Subjects" if subjects else Path(data_path)


def get_iblrig_path() -> Path or None:
    return Path(iblrig.__file__).parents[1]


def get_iblrig_test_fixtures() -> Path or None:
    return get_iblrig_path().joinpath("test", "fixtures")


def get_iblrig_params_path() -> Path or None:
    return get_iblrig_path().joinpath("pybpod_fixtures")


def get_iblrig_temp_alyx_path() -> Path or None:
    """
    Get the iblrig_local_data_path configured in the settings/iblrig_params.yaml file
    If none is found returns ~/iblrig_data/local
    """
    alyx_path = IBLRIG_SETTINGS.get("iblrig_temp_alyx_path")
    alyx_path = alyx_path or Path(iblrig.__file__).parents[1].joinpath('settings', 'alyx')
    return Path(alyx_path)


def get_commit_hash(folder: str):
    here = os.getcwd()
    os.chdir(folder)
    out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    os.chdir(here)
    if not out:
        log.debug("Commit hash is empty string")
    log.debug(f"Found commit hash {out}")
    return out


def get_water_calibration_func_file(latest: bool = True) -> Path or list:
    data_folder = get_iblrig_local_data_path()
    func_files = sorted(data_folder.rglob("_iblrig_calibration_water_function.csv"))
    if not func_files:
        return Path()
    return func_files[-1] if latest else func_files


def get_water_calibration_range_file(latest=True) -> Path or list:
    data_folder = get_iblrig_local_data_path()
    range_files = sorted(data_folder.rglob("_iblrig_calibration_water_range.csv"))
    if not range_files:
        return Path()
    return range_files[-1] if latest else range_files


def load_water_calibraition_func_file(fpath: str or Path) -> dict or None:
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


def get_bonsai_path(use_iblrig_bonsai: bool = True) -> str:
    """Checks for Bonsai folder in iblrig. Returns string with bonsai executable path."""
    iblrig_folder = get_iblrig_path()
    bonsai_folder = next((folder for folder in Path(
        iblrig_folder).glob('*') if folder.is_dir() and 'Bonsai' in folder.name), None)
    if bonsai_folder is None:
        return
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
        out = str(1).zfill(3)
    else:
        out = str(max(session_nums) + 1).zfill(3)
    log.debug(f"Setting session number to: {out}")

    return out


def get_pregen_session_folder() -> str:
    iblrig_path = get_iblrig_path()
    return str(iblrig_path / "pybpod_fixtures" / "IBL" / "tasks" / "_iblrig_tasks_ephysChoiceWorld" / "sessions")


class SessionPathCreator(object):
    # add subject name and protocol (maybe have a metadata struct)
    def __init__(self, subject_name, protocol=False, make=False):

        self.IBLRIG_FOLDER = get_iblrig_path()
        self.IBLRIG_EPHYS_SESSION_FOLDER = get_pregen_session_folder()
        self._BOARD = pybpod_params.get_board_name()

        self._PROTOCOL = protocol

        self.IBLRIG_SETTINGS_FOLDER = get_iblrig_params_path()
        self.IBLRIG_DATA_FOLDER = get_iblrig_local_data_path(subjects=False)
        self.IBLRIG_DATA_SUBJECTS_FOLDER = get_iblrig_local_data_path(subjects=True)

        self.SUBJECT_NAME = subject_name
        self.SUBJECT_FOLDER = self.IBLRIG_DATA_SUBJECTS_FOLDER.joinpath(self.SUBJECT_NAME)

        self.BONSAI = get_bonsai_path(use_iblrig_bonsai=True)
        self.VISUAL_STIM_FOLDER = self.IBLRIG_FOLDER / "visual_stim"

        self.SESSION_DATETIME = datetime.datetime.now().isoformat()
        self.SESSION_DATE = datetime.datetime.now().date().isoformat()

        self.SESSION_DATE_FOLDER = os.path.join(self.SUBJECT_FOLDER, self.SESSION_DATE)

        # TODO: check server to see if a session has already run today, intention is to decide
        #  what the next session number will be; this will occur in the get_session_number
        #  function (will likely be a separate issue/branch)
        self.SESSION_NUMBER = get_session_number(self.SESSION_DATE_FOLDER)

        self.SESSION_FOLDER = Path(self.SESSION_DATE_FOLDER) / self.SESSION_NUMBER
        self.SESSION_RAW_DATA_FOLDER = self.SESSION_FOLDER / "raw_behavior_data"
        self.SESSION_RAW_VIDEO_DATA_FOLDER = self.SESSION_FOLDER / "raw_video_data"
        self.SESSION_RAW_EPHYS_DATA_FOLDER = self.SESSION_FOLDER / "raw_ephys_data"
        self.SESSION_RAW_IMAGING_DATA_FOLDER = self.SESSION_FOLDER / "raw_imaging_data"
        self.SESSION_RAW_PASSIVE_DATA_FOLDER = self.SESSION_FOLDER / "raw_passive_data"

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
        # Water calibration files
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
        if make:
            self.make_missing_folders(make)
        self.display_logs()
        self.PREVIOUS_DATA_FILE = None

    def make_missing_folders(self, makelist):
        """
        makelist = True will make default folders with only raw_behavior_data
        makelist = False will not make any folders
        makelist = [list] will make the default folders and the raw_folders
        that are specific in the list
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
                if k == "PREVIOUS_DATA_FILE" and "training" in self._PROTOCOL:
                    msg = """
        ##########################################
            NOT FOUND: PREVIOUS_DATA_FILE
        ##########################################
                    USING INIT VALUES
        ##########################################"""
                    log.warning(msg)


if __name__ == "__main__":
    # spc = SessionPathCreator('C:\\iblrig', None, '_iblrig_test_mouse',
    # 'trainingChoiceWorld')
    # '/coder/mnt/nbonacchi/iblrig', None,
    spc = SessionPathCreator("_iblrig_test_mouse", protocol="passiveChoiceWorld", make=False)

    print("")
    for k in spc.__dict__:
        print(f"{k}: {spc.__dict__[k]}")

    print(".")


def load_pybpod_settings_yaml(file_name) -> Bunch:
    """
    Load pbpod settings from yaml file, and deserialize some of the PYBPOD parameters written in json format
    :param user_settings_yaml:
    :return:
    """
    rs = load_settings_yaml(file_name)
    # deserialize some of the PYBPOD parameters written in json format
    rs['PYBPOD_CREATOR'] = json.loads(rs['PYBPOD_CREATOR'])
    rs['PYBPOD_USER_EXTRA'] = json.loads(rs['PYBPOD_USER_EXTRA'])
    rs['PYBPOD_SUBJECTS'] = [json.loads(x.replace("'", '"')) for x in rs.pop('PYBPOD_SUBJECTS')][0]
    rs['PYBPOD_SUBJECT_EXTRA'] = [json.loads(x.replace("'", '"')) for x in rs['PYBPOD_SUBJECT_EXTRA'][1:-1].split('","')][0]
    return Bunch(rs)
