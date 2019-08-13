#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, November 14th 2018, 10:40:43 am
import datetime
import json
import logging
import os
import subprocess
from pathlib import Path

from ibllib.graphic import strinput
from ibllib.io import raw_data_loaders as raw
from pybpodgui_api.models.project import Project

import iblrig.logging_  # noqa

logger = logging.getLogger('iblrig')


class SessionPathCreator(object):
    # add subject name and protocol (maybe have a metadata struct)
    def __init__(self, iblrig_folder, iblrig_data_folder, subject_name,
                 protocol=False, board=False, make=False):
        self.IBLRIG_FOLDER = str(Path(iblrig_folder))
        self.IBLRIG_EPHYS_SESSION_FOLDER = str(
            Path(self.IBLRIG_FOLDER) / 'tasks' /
            '_iblrig_tasks_ephysChoiceWorld' / 'sessions')
        self._BOARD = board
        self._PROTOCOL = protocol
        self.IBLRIG_COMMIT_HASH = self._get_commit_hash(self.IBLRIG_FOLDER)
        self.IBLRIG_VERSION_TAG = self._get_version_tag(self.IBLRIG_FOLDER)

        self.IBLRIG_PARAMS_FOLDER = str(
            Path(self.IBLRIG_FOLDER).parent / 'iblrig_params')
        self.IBLRIG_DATA_FOLDER = self._iblrig_data_folder_init(
            self.IBLRIG_FOLDER, iblrig_data_folder)
        self.IBLRIG_DATA_SUBJECTS_FOLDER = str(
            Path(self.IBLRIG_DATA_FOLDER) / 'Subjects')

        self.VISUAL_STIM_FOLDER = str(Path(self.IBLRIG_FOLDER) / 'visual_stim')
        self.BONSAI = self.get_bonsai_path(use_iblrig_bonsai=True)
        self.VISUAL_STIMULUS_TYPE = self._visual_stim_type()
        self.VISUAL_STIMULUS_FILE = str(
            Path(self.VISUAL_STIM_FOLDER) /
            self.VISUAL_STIMULUS_TYPE / 'Gabor2D.bonsai')

        self.VIDEO_RECORDING_FOLDER = os.path.join(
            self.IBLRIG_FOLDER, 'devices', 'camera_recordings')
        self.VIDEO_RECORDING_FILE = os.path.join(
            self.VIDEO_RECORDING_FOLDER, 'one_camera.bonsai')

        self.SUBJECT_NAME = subject_name
        self.SUBJECT_FOLDER = os.path.join(
            self.IBLRIG_DATA_SUBJECTS_FOLDER, self.SUBJECT_NAME)

        self.SESSION_DATETIME = datetime.datetime.now()
        self.SESSION_DATE = self.SESSION_DATETIME.date().isoformat()
        self.SESSION_DATETIME = self.SESSION_DATETIME.isoformat()

        self.SESSION_DATE_FOLDER = os.path.join(
            self.SUBJECT_FOLDER, self.SESSION_DATE)

        self.SESSION_NUMBER = self._session_number()

        self.SESSION_FOLDER = str(
            Path(self.SESSION_DATE_FOLDER) / self.SESSION_NUMBER)
        self.SESSION_RAW_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_behavior_data')
        self.SESSION_RAW_VIDEO_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_video_data')
        self.SESSION_RAW_EPHYS_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_ephys_data')
        self.SESSION_RAW_IMAGING_DATA_FOLDER = os.path.join(
            self.SESSION_FOLDER, 'raw_imaging_data')

        self.SESSION_NAME = '{}'.format(os.path.sep).join(
            [self.SUBJECT_NAME, self.SESSION_DATE, self.SESSION_NUMBER])

        self.BASE_FILENAME = '_iblrig_task'
        self.SETTINGS_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                               self.BASE_FILENAME +
                                               'Settings.raw.json')
        self.DATA_FILE_PATH = os.path.join(self.SESSION_RAW_DATA_FOLDER,
                                           self.BASE_FILENAME +
                                           'Data.raw.jsonable')

        self.LATEST_WATER_CALIBRATION_FILE = self._latest_water_calib_file()
        self.LATEST_WATER_CALIB_RANGE_FILE = self._latest_water_range_file()
        self.LATEST_SCREEN_CALIBRATION_FILE = self._latest_screen_calib_file()

        self.PREVIOUS_DATA_FILE = self._previous_data_file()
        self.PREVIOUS_SETTINGS_FILE = self._previous_settings_file()
        self.PREVIOUS_SESSION_PATH = self._previous_session_path()

        self.BPOD_COMPORTS_FILE = str(
            Path(self.IBLRIG_PARAMS_FOLDER) / '.bpod_comports.json')
        if make:
            self.make_missing_folders(make)

        self.COM = self._init_com()
        self._check_com_config()

        self.display_logs()

    def make_missing_folders(self, makelist):
        if isinstance(makelist, bool):
            logger.debug(f"Making default folders")
            self.make_folder(self.IBLRIG_DATA_FOLDER)
            self.make_folder(self.IBLRIG_DATA_SUBJECTS_FOLDER)
            self.make_folder(self.SUBJECT_FOLDER)
            self.make_folder(self.SESSION_DATE_FOLDER)
            self.make_folder(self.SESSION_FOLDER)
            self.make_folder(self.SESSION_RAW_DATA_FOLDER)
        elif isinstance(makelist, list):
            logger.debug(f"Making extra folders for {makelist}")
            self.make_missing_folders(True)
            if 'video' in makelist:
                self.make_folder(self.SESSION_RAW_VIDEO_DATA_FOLDER)
            if 'ephys' in makelist:
                self.make_folder(self.SESSION_RAW_EPHYS_DATA_FOLDER)
            if 'imag' in makelist:
                self.make_folder(self.SESSION_RAW_IMAGING_DATA_FOLDER)

        return

    def _visual_stim_type(self):
        if 'habituation' in self._PROTOCOL or 'sync_test' in self._PROTOCOL:
            return 'GaborHabituationTask'
        elif 'ephys_certification' in self._PROTOCOL:
            return 'ephys_certification'
        else:
            return 'GaborIBLTask'

    def _init_com(self) -> dict:
        logger.debug("Initializing COM ports")
        p = Project()
        p.load(str(Path(self.IBLRIG_PARAMS_FOLDER) / 'IBL'))
        out = None
        if Path(self.BPOD_COMPORTS_FILE).exists():
            logger.debug(
                f"Found COM port definition file: {self.BPOD_COMPORTS_FILE}")
            # If file exists open file
            with open(self.BPOD_COMPORTS_FILE, 'r') as f:
                out = json.load(f)
            # Use the GUI defined COM port for BPOD
            out['BPOD'] = p.boards[0].serial_port
            logger.debug(f".bpod_comports.json exists with content: {out}")
        else:
            logger.debug(f"NOT FOUND: COM ports definition file")
            # If no file exists create empty file
            comports = {
                'BPOD': None, 'ROTARY_ENCODER': None, 'FRAME2TTL': None}
            comports['BPOD'] = p.boards[0].serial_port
            out = comports
            logger.debug(f"Calling create with comports: {comports}")
            self.create_bpod_comport_file(self.BPOD_COMPORTS_FILE, comports)
        return out

    def _check_com_config(self):
        comports = {'BPOD': self.COM['BPOD'], 'ROTARY_ENCODER': None,
                    'FRAME2TTL': None}
        logger.debug(f"COMPORTS: {str(self.COM)}")
        if not self.COM['ROTARY_ENCODER']:
            comports['ROTARY_ENCODER'] = strinput(
                "RIG CONFIG",
                "Please insert ROTARY ENCODER COM port (e.g. COM9): ",
                default='COM')
            logger.debug("Updating comport file with ROTARY_ENCODER port " +
                         f"{comports['ROTARY_ENCODER']}")
            self.create_bpod_comport_file(self.BPOD_COMPORTS_FILE, comports)
            self.COM = comports
        if not self.COM['FRAME2TTL']:
            comports['FRAME2TTL'] = strinput(
                "RIG CONFIG",
                "Please insert FRAME2TTL COM port (e.g. COM9): ", default='COM'
            )
            logger.debug("Updating comport file with FRAME2TTL port " +
                         f"{comports['FRAME2TTL']}")
            self.create_bpod_comport_file(self.BPOD_COMPORTS_FILE, comports)
            self.COM = comports

    def _get_ibllib_folder(self):
        import ibllib
        fpath = Path(ibllib.__file__).parent.parent
        return str(fpath)

    def _get_commit_hash(self, repo_path):
        here = os.getcwd()
        os.chdir(repo_path)
        out = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode()
        os.chdir(here)
        if not out:
            logger.debug("Commit hash is empty string")
        logger.debug(f"Found commit hash {out}")
        return out.strip()

    def _get_version_tag(self, repo_path):
        here = os.getcwd()
        os.chdir(repo_path)
        tag = subprocess.check_output(["git", "tag",
                                       "--points-at", "HEAD"]).decode().strip()
        os.chdir(here)
        if not tag:
            logger.debug(f"NOT FOUND: Version TAG for {repo_path}")
        logger.debug(f"Found version tag {tag}")
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
            logger.debug(
                f"NOT FOUND: {preexisting_bonsai}. Using packaged Bonsai")
            BONSAI = ibl_bonsai
        logger.debug(f"Found Bonsai executable: {BONSAI}")

        return BONSAI

    @staticmethod
    def create_bpod_comport_file(fpath: str or Path, comports: dict):
        with open(fpath, 'w') as f:
            json.dump(comports, f, indent=1)
        logger.debug(f"COM port definition file created {comports} in {fpath}")
        return

    @staticmethod
    def make_folder(str1):
        """Check if folder path exists and if not create it + parents."""
        path = Path(str1)
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created folder {path}")

    @staticmethod
    def get_subfolder_paths(folder):
        out = [os.path.join(folder, x) for x in os.listdir(folder)
               if os.path.isdir(os.path.join(folder, x))]
        logger.debug(f"Found {len(out)} subfolders for folder {folder}")

        return out

    def _iblrig_folder_init(self):
        logger.debug(
            f"Ensuring <{os.sep}> separator for folder {self.IBLRIG_FOLDER}")
        if '/' in self.IBLRIG_FOLDER:
            p = '{}'.format(os.path.sep).join(self.IBLRIG_FOLDER.split('/'))
        elif '\\' in self.IBLRIG_FOLDER:
            p = '{}'.format(os.path.sep).join(self.IBLRIG_FOLDER.split('\\'))
        return p

    def _iblrig_data_folder_init(self, iblrig_folder, iblrig_data_folder):
        logger.debug("Initializing data folder")
        iblrig_folder = Path(iblrig_folder)
        if not iblrig_folder.exists():
            logger.error("Couldn't find IBLRIG_FOLDER on filesystem")
            raise IOError

        if iblrig_data_folder is None:
            out = iblrig_folder.parent / 'iblrig_data'
            logger.debug(f"Setting data folder to default location: {out}")
            return str(out)
        else:
            mdf = Path(iblrig_data_folder)
            if mdf.name == 'Subjects':
                out = str(mdf.parent)
            elif mdf.name != 'Subjects':
                out = str(mdf)
            logger.debug(f"Setting data folder to location: {out}")
            return out

    def _session_number(self) -> str:
        logger.debug("Initializing session number")
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
        logger.debug(f"Setting session number to: {out}")

        return out

    def _previous_session_folders(self):
        """
        """
        logger.debug("Looking for previous session folders")
        sess_folders = []
        subj_folder = Path(self.SUBJECT_FOLDER)
        subj_name = subj_folder.name
        if not subj_folder.exists():
            logger.debug(
                f'NOT FOUND: No previous sessions for subject {subj_name}')
            return sess_folders

        for date in self.get_subfolder_paths(self.SUBJECT_FOLDER):
            sess_folders.extend(self.get_subfolder_paths(date))

        sess_folders = [x for x in sorted(sess_folders)
                        if self.SESSION_FOLDER not in x]
        if not sess_folders:
            logger.debug(
                f'NOT FOUND: No previous sessions for subject {subj_name}')

        logger.debug(
            f"Found {len(sess_folders)} session folders for mouse {subj_name}")

        return sess_folders

    def _previous_data_files(self, typ='data'):
        logger.debug(f"Looking for previous files of type: {typ}")
        prev_data_files = []
        prev_session_files = []
        data_fname = self.BASE_FILENAME + 'Data.raw.jsonable'
        settings_fname = self.BASE_FILENAME + 'Settings.raw.json'
        logger.debug(f"Looking for files:{data_fname} AND {settings_fname}")
        for prev_sess_path in self._previous_session_folders():
            prev_sess_path = Path(prev_sess_path) / 'raw_behavior_data'
            # Get all data and settings file if they both exist
            if ((prev_sess_path / data_fname).exists() and
                    (prev_sess_path / settings_fname).exists()):
                prev_data_files.append(prev_sess_path / data_fname)
                prev_session_files.append(prev_sess_path / settings_fname)
        logger.debug(f"Found {len(prev_data_files)} file pairs")
        # Remove empty files
        ds_out = [(d, s) for d, s in zip(prev_data_files, prev_session_files)
                  if d.stat().st_size != 0 and s.stat().st_size != 0]
        logger.debug(f"Found {len(ds_out)} non empty file pairs")
        # Remove sessions of different task protocols
        ds_out = [(d, s) for d, s in ds_out if self._PROTOCOL in
                  raw.load_settings(str(s.parent.parent))['PYBPOD_PROTOCOL']]
        logger.debug(
            f"Found {len(ds_out)} file pairs for protocol {self._PROTOCOL}")
        data_out = [str(d) for d, s in ds_out]
        settings_out = [str(s) for d, s in ds_out]
        if not data_out:
            logger.debug(
                f'NOT FOUND: Previous data files for task {self._PROTOCOL}')
        if not settings_out:
            logger.debug(
                f'NOT FOUND: Previous settings files for task {self._PROTOCOL}')
        logger.debug(f"Reurning {typ} files")

        return data_out if typ == 'data' else settings_out

    def _previous_data_file(self):
        logger.debug("Getting previous data file")
        out = sorted(self._previous_data_files())
        if out:
            logger.debug(f"Previous data file: {out[-1]}")
            return out[-1]
        else:
            logger.debug("NOT FOUND: Previous data file")
            return None

    def _previous_settings_file(self):
        logger.debug("Getting previous settings file")
        out = sorted(self._previous_data_files(typ='settings'))
        if out:
            logger.debug(f"Previous settings file: {out[-1]}")
            return out[-1]
        else:
            logger.debug("NOT FOUND: Previous settings file")
            return None

    def _previous_session_path(self):
        logger.debug("Getting previous session path")
        if self.PREVIOUS_DATA_FILE is not None:
            out = str(Path(self.PREVIOUS_DATA_FILE).parent.parent)
            logger.debug(f"Previous session path: {out}")
        else:
            out = None
            logger.debug("NOT FOUND: Previous session path")

        return out

    def _latest_screen_calib_file(self):
        logger.debug(f"Looking for screen calibration files: {self._BOARD}")
        dsf = Path(self.IBLRIG_DATA_SUBJECTS_FOLDER)
        cal = dsf / '_iblrig_calibration'
        if not cal.exists():
            logger.debug(f'NOT FOUND: Calibration subject {str(cal)}')
            return None

        return None

    def _latest_water_calib_file(self):
        logger.debug(f"Looking for calibration file of board: {self._BOARD}")
        dsf = Path(self.IBLRIG_DATA_SUBJECTS_FOLDER)
        cal = dsf / '_iblrig_calibration'
        if not cal.exists():
            logger.debug(f'NOT FOUND: Calibration subject {str(cal)}')
            return None

        if not self._BOARD:
            logger.debug(f'NOT FOUND: Board {str(self._BOARD)}')
            return None

        cal_session_folders = []
        for date in self.get_subfolder_paths(str(cal)):
            cal_session_folders.extend(self.get_subfolder_paths(date))
        logger.debug(f"Found {len(cal_session_folders)} calibration sessions")

        water_cal_files = []
        for session in cal_session_folders:
            session = Path(session) / 'raw_behavior_data'
            water_cal_files.extend(list(session.glob(
                '_iblrig_calibration_water_function.csv')))

        water_cal_files = sorted(water_cal_files,
                                 key=lambda x: int(x.parent.parent.name))
        logger.debug(
            f"Found {len(water_cal_files)} calibration sessions for water")

        # Should add check for file.stat().st_size != 0
        if not water_cal_files:
            logger.debug(
                f'NOT FOUND: Water calibration files for board {self._BOARD}')
            return

        water_cal_settings = [x.parent / "_iblrig_taskSettings.raw.json"
                              for x in water_cal_files]
        logger.debug(f"Found {len(water_cal_settings)} settings files")
        same_board_cal_files = []
        for fcal, s in zip(water_cal_files, water_cal_settings):
            if s.exists():
                settings = raw.load_settings(str(s.parent.parent))
                if settings['PYBPOD_BOARD'] == self._BOARD:
                    same_board_cal_files.append(fcal)
                else:
                    logger.debug(
                        f'NOT FOUND: PYBPOD_BOARD in settings file {str(s)}')

            else:
                logger.debug(
                    f'NOT FOUND: Settings file for data file {str(fcal)}.')

        same_board_cal_files = sorted(same_board_cal_files,
                                      key=lambda x: int(x.parent.parent.name))
        logger.debug(
            f"Found {len(same_board_cal_files)} files for board {self._BOARD}")
        if same_board_cal_files:
            logger.debug(
                f"Latest water calibration file: {same_board_cal_files[-1]}")
            return str(same_board_cal_files[-1])
        else:
            logger.debug(f'No valid calibration files were found for board {self._BOARD}')
            return

    def _latest_water_range_file(self):
        if self.LATEST_WATER_CALIBRATION_FILE is None:
            return

        wcfile = Path(self.LATEST_WATER_CALIBRATION_FILE)
        wcrange = wcfile.parent / '_iblrig_calibration_water_range.csv'
        if wcrange.exists():
            return str(wcrange)
        else:
            return

    def display_logs(self):
        # User info and warnings
        for k in self.__dict__:
            if not self.__dict__[k]:
                logger.info(f"NOT FOUND: {k}")
                if k == 'IBLRIG_VERSION_TAG':
                    msg = """
        ##########################################
            NOT FOUND: IBLRIG_VERSION_TAG
        ##########################################
        You appear to be on an uncommitted version
        of iblrig. Please run iblrig/update.py to
        check which is the latest version.
        ##########################################"""
                    logger.warning(msg)

                if k == 'PREVIOUS_DATA_FILE':
                    msg = """
        ##########################################
            NOT FOUND: PREVIOUS_DATA_FILE
        ##########################################
                    USING INIT VALUES
        ##########################################"""
                    logger.warning(msg)
                if k == 'LATEST_WATER_CALIBRATION_FILE':
                    msg = """
        ##########################################
         NOT FOUND: LATEST_WATER_CALIBRATION_FILE
        ##########################################"""
                    logger.warning(msg)
                if k == 'LATEST_WATER_CALIB_RANGE_FILE':
                    msg = """
        ##########################################
         NOT FOUND: LATEST_WATER_CALIB_RANGE_FILE
        ##########################################
                    Using full range
        ##########################################
        """
                    logger.warning(msg)


if __name__ == "__main__":
    # spc = SessionPathCreator('C:\\iblrig', None, '_iblrig_test_mouse',
    # 'trainingChoiceWorld')
    # '/coder/mnt/nbonacchi/iblrig', None,
    spc = SessionPathCreator(
        '/home/nico/Projects/IBL/github/iblrig',
        '/home/nico/Projects/IBL/github/iblrig_data',
        '_iblrig_test_mouse', protocol='trainingChoiceWorld',
        board='_iblrig_mainenlab_behavior_0', make=['video', 'ephys', 'imag'])

    print("")
    for k in spc.__dict__:
        print(f"{k}: {spc.__dict__[k]}")

    print('.')
