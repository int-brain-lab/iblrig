"""
Commonalities for all tasks.

This module provides hardware mixins that can be used together with BaseSession to compose tasks.
This module tries to exclude task related logic.
"""

import argparse
import contextlib
import datetime
import importlib.metadata
import inspect
import json
import logging
import signal
import sys
import time
import traceback
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, final, Any

import numpy as np
import pandas as pd
import serial
import yaml
from pydantic import create_model
from pydantic_settings import BaseSettings, SettingsConfigDict
from pythonosc import udp_client

import ibllib.io.session_params as ses_params
import iblrig.graphic as graph
import iblrig.path_helper
import pybpodapi
from ibllib.oneibl.registration import IBLRegistrationClient
from iblrig import net, path_helper, sound
from iblrig.constants import BASE_PATH, BONSAI_EXE, PYSPIN_AVAILABLE
from iblrig.frame2ttl import Frame2TTL
from iblrig.hardware import SOFTCODE, Bpod, MyRotaryEncoder, sound_device_factory
from iblrig.hifi import HiFi
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings, TrialDataModel
from iblrig.tools import call_bonsai
from iblrig.transfer_experiments import BehaviorCopier, VideoCopier
from iblrig.valve import Valve
from iblutil.io.net.base import ExpMessage
from iblutil.spacer import Spacer
from iblutil.util import Bunch, flatten, setup_logger
from one.alf.io import next_num_folder
from one.api import ONE, OneAlyx
from pybpodapi.protocol import StateMachine

OSC_CLIENT_IP = '127.0.0.1'

log = logging.getLogger(__name__)


class HasBpod(Protocol):
    bpod: Bpod

class BaseSession(ABC):
    version = None
    """str: !!CURRENTLY UNUSED!! task version string."""
    # protocol_name: str | None = None
    """str: The name of the task protocol (NB: avoid spaces)."""
    base_parameters_file: Path | None = None
    """Path: A YAML file containing base, default task parameters."""
    is_mock = False
    """list of str: One or more ibllib.pipes.tasks.Task names for task extraction."""
    logger: logging.Logger = None
    """logging.Logger: Log instance used solely to keep track of log level passed to constructor."""
    experiment_description: dict = {}
    """dict: The experiment description."""
    extractor_tasks: list | None = None
    """list of str: An optional list of pipeline task class names to instantiate when preprocessing task data."""

    TrialDataModel: type[TrialDataModel]

    @property
    @abstractmethod
    def protocol_name(self) -> str: ...

    def __init__(
        self,
        subject=None,
        task_parameter_file=None,
        file_hardware_settings=None,
        hardware_settings: HardwareSettings = None,
        file_iblrig_settings=None,
        iblrig_settings: RigSettings = None,
        one=None,
        interactive=True,
        projects=None,
        procedures=None,
        stub=None,
        subject_weight_grams=None,
        append=False,
        wizard=False,
        log_level='INFO',
        **kwargs,
    ):
        """
        :param subject: The subject nickname. Required.
        :param task_parameter_file: an optional path to the task_parameters.yaml file
        :param file_hardware_settings: name of the hardware file in the settings folder, or full file path
        :param hardware_settings: an optional dictionary of hardware settings. Keys will override any keys in the file
        :param file_iblrig_settings: name of the iblrig file in the settings folder, or full file path
        :param iblrig_settings: an optional dictionary of iblrig settings. Keys will override any keys in the file
        :param one: an optional instance of ONE
        :param interactive:
        :param projects: An optional list of Alyx protocols.
        :param procedures: An optional list of Alyx procedures.
        :param subject_weight_grams: weight of the subject
        :param stub: A full path to an experiment description file containing experiment information.
        :param append: bool, if True, append to the latest existing session of the same subject for the same day
        """
        self.extractor_tasks = getattr(self, 'extractor_tasks', None)
        self._logger = None
        self._setup_loggers(level=log_level)
        if not isinstance(self, EmptySession):
            log.info(f'Running iblrig {iblrig.__version__}, pybpod version {pybpodapi.__version__}')
        log.info(f'Session call: {" ".join(sys.argv)}')
        self.interactive = interactive
        self._one = one
        self.init_datetime = datetime.datetime.now()

        # loads in the settings: first load the files, then update with the input argument if provided
        self.hardware_settings: HardwareSettings = load_pydantic_yaml(HardwareSettings, file_hardware_settings)
        if hardware_settings is not None:
            self.hardware_settings.update(hardware_settings)
            HardwareSettings.model_validate(self.hardware_settings)
        self.iblrig_settings: RigSettings = load_pydantic_yaml(RigSettings, file_iblrig_settings)
        if iblrig_settings is not None:
            self.iblrig_settings.update(iblrig_settings)
            RigSettings.model_validate(self.iblrig_settings)

        self.wizard = wizard

        # Load the tasks settings, from the task folder or override with the input argument
        self.task_params = self.read_task_parameter_files(task_parameter_file)

        self.session_info = Bunch(
            {
                'NTRIALS': 0,
                'NTRIALS_CORRECT': 0,
                'PROCEDURES': procedures,
                'PROJECTS': projects,
                'SESSION_START_TIME': self.init_datetime.isoformat(),
                'SESSION_END_TIME': None,
                'SESSION_NUMBER': 0,
                'SUBJECT_NAME': subject,
                'SUBJECT_WEIGHT': subject_weight_grams,
                'TOTAL_WATER_DELIVERED': 0,
            }
        )
        # Executes mixins init methods
        self._execute_mixins_shared_function('init_mixin')
        self.paths = self._init_paths(append=append)
        if not isinstance(self, EmptySession):
            log.info(f'Session raw data: {self.paths.SESSION_RAW_DATA_FOLDER}')
        # Prepare the experiment description dictionary
        self.experiment_description = self.make_experiment_description_dict(
            self.protocol_name,
            self.paths.get('TASK_COLLECTION'),
            procedures,
            projects,
            self.hardware_settings,
            stub,
            extractors=self.extractor_tasks,
        )

    @classmethod
    def get_task_file(cls) -> Path:
        """
        Get the path to the task's python file.

        Returns
        -------
        Path
            The path to the task file.
        """
        return Path(inspect.getfile(cls))

    @classmethod
    def get_task_directory(cls) -> Path:
        """
        Get the path to the task's directory.

        Returns
        -------
        Path
            The path to the task's directory.
        """
        return cls.get_task_file().parent

    @classmethod
    def read_task_parameter_files(cls, task_parameter_file: str | Path | None = None) -> Bunch:
        """
        Get the task's parameters from the various YAML files in the hierarchy.

        Parameters
        ----------
        task_parameter_file : str or Path, optional
            Path to override the task parameter file

        Returns
        -------
        Bunch
            Task parameters
        """
        # Load the tasks settings, from the task folder or override with the input argument
        base_parameters_files = [task_parameter_file or cls.get_task_directory().joinpath('task_parameters.yaml')]

        # loop through the task hierarchy to gather parameter files
        for c in cls.__mro__:
            base_file = getattr(c, 'base_parameters_file', None)
            if base_file is not None:
                base_parameters_files.append(base_file)

        # remove list duplicates while preserving order, we want the highest order first
        base_parameters_files = list(reversed(list(dict.fromkeys(base_parameters_files))))

        # loop through files and update the dictionary, the latest files in the hierarchy have precedence
        task_params = dict()
        for param_file in base_parameters_files:
            if Path(param_file).exists():
                with open(param_file) as fp:
                    params = yaml.safe_load(fp)
                if params is not None:
                    task_params.update(params)

        # at last sort the dictionary so itś easier for a human to navigate the many keys, return as a Bunch
        return Bunch(sorted(task_params.items()))

    def _init_paths(self, append: bool = False) -> Bunch:
        r"""
        Initialize session paths.

        Parameters
        ----------
        append : bool
            Iterate task collection within today's most recent session folder for the selected subject, instead of
            iterating session number.

        Returns
        -------
        Bunch
            Bunch with keys:

            *   BONSAI: full path to the bonsai executable
                `C:\iblrigv8\Bonsai\Bonsai.exe`
            *   VISUAL_STIM_FOLDER: full path to the visual stimulus folder
                `C:\iblrigv8\visual_stim`
            *   LOCAL_SUBJECT_FOLDER: full path to the local subject folder
                `C:\iblrigv8_data\mainenlab\Subjects`
            *   REMOTE_SUBJECT_FOLDER: full path to the remote subject folder
                `Y:\Subjects`
            *   SESSION_FOLDER: full path to the current session:
                `C:\iblrigv8_data\mainenlab\Subjects\SWC_043\2019-01-01\001`
            *   TASK_COLLECTION: folder name of the current task
                `raw_task_data_00`
            *   SESSION_RAW_DATA_FOLDER: concatenation of the session folder and the task collection.
                This is where the task data gets written
                `C:\iblrigv8_data\mainenlab\Subjects\SWC_043\2019-01-01\001\raw_task_data_00`
            *   DATA_FILE_PATH: contains the bpod trials
                `C:\iblrigv8_data\mainenlab\Subjects\SWC_043\2019-01-01\001\raw_task_data_00\_iblrig_taskData.raw.jsonable`
            *   SETTINGS_FILE_PATH: contains the task settings
                `C:\iblrigv8_data\mainenlab\Subjects\SWC_043\2019-01-01\001\raw_task_data_00\_iblrig_taskSettings.raw.json`
        """
        rig_computer_paths = path_helper.get_local_and_remote_paths(
            local_path=self.iblrig_settings.iblrig_local_data_path,
            remote_path=self.iblrig_settings.iblrig_remote_data_path,
            lab=self.iblrig_settings.ALYX_LAB,
            iblrig_settings=self.iblrig_settings,
        )
        paths = Bunch({'IBLRIG_FOLDER': BASE_PATH})
        paths.BONSAI = BONSAI_EXE
        paths.VISUAL_STIM_FOLDER = BASE_PATH.joinpath('visual_stim')
        paths.LOCAL_SUBJECT_FOLDER = rig_computer_paths['local_subjects_folder']
        paths.REMOTE_SUBJECT_FOLDER = rig_computer_paths['remote_subjects_folder']
        # initialize the session path
        date_folder = paths.LOCAL_SUBJECT_FOLDER.joinpath(
            self.session_info.SUBJECT_NAME, self.session_info.SESSION_START_TIME[:10]
        )
        if append:
            # this is the case where we append a new protocol to an existing session
            todays_sessions = sorted(filter(Path.is_dir, date_folder.glob('*')), reverse=True)
            assert len(todays_sessions) > 0, f'Trying to chain a protocol, but no session folder found in {date_folder}'
            paths.SESSION_FOLDER = todays_sessions[0]
            paths.TASK_COLLECTION = iblrig.path_helper.iterate_collection(paths.SESSION_FOLDER)
            if self.hardware_settings.get('MAIN_SYNC', False) and not paths.TASK_COLLECTION.endswith('00'):
                """
                Chained protocols make little sense when Bpod is the main sync as there is no
                continuous acquisition between protocols.  Only one sync collection can be defined in
                the experiment description file.
                If you are running experiments with an ephys rig (nidq) or an external daq, you should
                correct the MAIN_SYNC parameter in the hardware settings file in ./settings/hardware_settings.yaml
                """
                raise RuntimeError('Chained protocols not supported for bpod-only sessions')
        else:
            # in this case the session path is created from scratch
            paths.SESSION_FOLDER = date_folder / next_num_folder(date_folder)
            paths.TASK_COLLECTION = iblrig.path_helper.iterate_collection(paths.SESSION_FOLDER)

        self.session_info.SESSION_NUMBER = int(paths.SESSION_FOLDER.name)
        paths.SESSION_RAW_DATA_FOLDER = paths.SESSION_FOLDER.joinpath(paths.TASK_COLLECTION)
        paths.DATA_FILE_PATH = paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable')
        paths.SETTINGS_FILE_PATH = paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        return paths

    @property
    def exp_ref(self):
        """Construct an experiment reference string from the session info attribute."""
        subject, date, number = (self.session_info[k] for k in ('SUBJECT_NAME', 'SESSION_START_TIME', 'SESSION_NUMBER'))
        if not all([subject, date, number]):
            return None
        return self.one.dict2ref(dict(subject=subject, date=date[:10], sequence=str(number)))

    def _setup_loggers(self, level='INFO', level_bpod='WARNING', file=None):
        self._logger = setup_logger('iblrig', level=level, file=file)  # logger attr used by create_session to determine log level
        setup_logger('pybpodapi', level=level_bpod, file=file)

    @staticmethod
    def _remove_file_loggers():
        for logger_name in ['iblrig', 'pybpodapi']:
            logger = logging.getLogger(logger_name)
            file_handlers = [fh for fh in logger.handlers if isinstance(fh, logging.FileHandler)]
            for fh in file_handlers:
                fh.close()
                logger.removeHandler(fh)

    @staticmethod
    def make_experiment_description_dict(
        task_protocol: str,
        task_collection: str,
        procedures: list = None,
        projects: list = None,
        hardware_settings: dict | HardwareSettings = None,
        stub: Path = None,
        extractors: list = None,
        camera_config: str = None,
    ):
        """
        Construct an experiment description dictionary.

        Parameters
        ----------
        task_protocol : str
            The task protocol name, e.g. _ibl_trainingChoiceWorld2.0.0.
        task_collection : str
            The task collection name, e.g. raw_task_data_00.
        procedures : list
            An optional list of Alyx procedures.
        projects : list
            An optional list of Alyx protocols.
        hardware_settings : dict
            An optional dict of hardware devices, loaded from the hardware_settings.yaml file.
        stub : dict
            An optional experiment description stub to update.
        extractors: list
            An optional list of extractor names for the task.
        camera_config : str
            The camera configuration name in the hardware settings. Defaults to the first key in
            'device_cameras'.

        Returns
        -------
        dict
            The experiment description.
        """
        description = ses_params.read_params(stub) if stub else {}

        # Add hardware devices
        if hardware_settings is not None:
            if isinstance(hardware_settings, HardwareSettings):
                hardware_settings = hardware_settings.model_dump()
            devices = {}
            cams = hardware_settings.get('device_cameras', None)
            if cams:
                devices['cameras'] = {}
                camera_config = camera_config or next((k for k in cams), {})
                devices.update(VideoCopier.config2stub(cams[camera_config])['devices'])
            if hardware_settings.get('device_microphone', None):
                devices['microphone'] = {'microphone': {'collection': task_collection, 'sync_label': 'audio'}}
            ses_params.merge_params(description, {'devices': devices})

        # Add projects and procedures
        description['procedures'] = list(set(description.get('procedures', []) + (procedures or [])))
        description['projects'] = list(set(description.get('projects', []) + (projects or [])))
        is_main_sync = (hardware_settings or {}).get('MAIN_SYNC', False)
        # Add sync key if required
        if is_main_sync and 'sync' not in description:
            description['sync'] = {
                'bpod': {'collection': task_collection, 'acquisition_software': 'pybpod', 'extension': '.jsonable'}
            }
        # Add task
        task = {task_protocol: {'collection': task_collection}}
        if not is_main_sync:
            task[task_protocol]['sync_label'] = 'bpod'
        if extractors:
            assert isinstance(extractors, list), 'extractors parameter must be a list of strings'
            task[task_protocol].update({'extractors': extractors})
        if 'tasks' not in description:
            description['tasks'] = [task]
        else:
            description['tasks'].append(task)
        return description

    def _make_task_parameters_dict(self):
        """
        Create dictionary that will be saved to the settings json file for extraction.

        Returns
        -------
        dict
            A dictionary that will be saved to the settings json file for extraction.
        """
        output_dict = dict(self.task_params)  # Grab parameters from task_params session
        output_dict.update(self.hardware_settings.model_dump())  # Update dict with hardware settings from session
        output_dict.update(dict(self.session_info))  # Update dict with session_info (subject, procedure, projects)
        patch_dict = {  # Various values added to ease transition from iblrig v7 to v8, different home may be desired
            'IBLRIG_VERSION': iblrig.__version__,
            'PYBPOD_PROTOCOL': self.protocol_name,
            'ALYX_USER': self.iblrig_settings.ALYX_USER,
            'ALYX_LAB': self.iblrig_settings.ALYX_LAB,
        }
        with contextlib.suppress(importlib.metadata.PackageNotFoundError):
            patch_dict['PROJECT_EXTRACTION_VERSION'] = importlib.metadata.version('project_extraction')
        output_dict.update(patch_dict)
        return output_dict

    def save_task_parameters_to_json_file(self, destination_folder: Path | None = None) -> Path:
        """
        Collects the various settings and parameters of the session and outputs them to a JSON file.

        Returns
        -------
        Path
            Path to the resultant JSON file
        """
        output_dict = self._make_task_parameters_dict()
        if destination_folder:
            json_file = destination_folder.joinpath('_iblrig_taskSettings.raw.json')
        else:
            json_file = self.paths['SETTINGS_FILE_PATH']
        json_file.parent.mkdir(parents=True, exist_ok=True)
        with open(json_file, 'w') as outfile:
            json.dump(output_dict, outfile, indent=4, sort_keys=True, default=str)  # converts datetime objects to string
        return json_file  # PosixPath

    @final
    def save_trial_data_to_json(self, bpod_data: dict):
        """Validate and save trial data.

        This method retrieve's the current trial's data from the trial_table and validates it using a Pydantic model
        (self.TrialDataDefinition). In merges in the trial's bpod_data dict and appends everything to the session's
        JSON data file.

        Parameters
        ----------
        bpod_data : dict
            Trial data returned from pybpod.
        """
        # get trial's data as a dict
        trial_data = self.trials_table.iloc[self.trial_num].to_dict()

        # warn about entries not covered by pydantic model
        if trial_data.get('trial_num', 1) == 0:
            for key in set(trial_data.keys()) - set(self.TrialDataModel.model_fields) - {'index'}:
                log.warning(
                    f'Key "{key}" in trial_data is missing from TrialDataModel - '
                    f'its value ({trial_data[key]}) will not be validated.'
                )

        # validate by passing through pydantic model
        trial_data = self.TrialDataModel.model_validate(trial_data).model_dump()

        # add bpod_data as 'behavior_data'
        trial_data['behavior_data'] = bpod_data

        # write json data to file
        with open(self.paths['DATA_FILE_PATH'], 'a') as fp:
            fp.write(json.dumps(trial_data) + '\n')

    @property
    def one(self):
        """ONE getter."""
        if self._one is None:
            if self.iblrig_settings['ALYX_URL'] is None:
                return
            info_str = (
                f"alyx client with user name {self.iblrig_settings['ALYX_USER']} "
                + f"and url: {self.iblrig_settings['ALYX_URL']}"
            )
            try:
                self._one = ONE(
                    base_url=str(self.iblrig_settings['ALYX_URL']),
                    username=self.iblrig_settings['ALYX_USER'],
                    mode='remote',
                    cache_rest=None,
                )
                log.info('instantiated ' + info_str)
            except Exception:
                log.error(traceback.format_exc())
                log.error('could not connect to ' + info_str)
        return self._one

    def register_to_alyx(self):
        """
        Registers the session to Alyx.

        This registers the session using the IBLRegistrationClient class.  This uses the settings
        file(s) and experiment description file to extract the session data.  This may be called
        any number of times and if the session record already exists in Alyx it will be updated.
        If session registration fails, it will be done before extraction in the ibllib pipeline.

        Note that currently the subject weight is registered once and only once.  The recorded
        weight of the first protocol run is used.

        Water administrations are added separately by this method: it is expected that
        `register_session` is first called with no recorded total water. This method will then add
        a water administration each time it is called, and should therefore be called only once
        after each protocol is run. If water administration registration fails for all protocols,
        this will be done before extraction in the ibllib pipline, however, if a water
        administration is successfully registered for one protocol and subsequent ones fail to
        register, these will not be added before extraction in ibllib and therefore must be
        manually added to Alyx.

        Returns
        -------
        dict
            The registered session record.

        See Also
        --------
        :external+iblenv:meth:`ibllib.oneibl.registration.IBLRegistrationClient.register_session` - The registration method.
        """
        if self.session_info['SUBJECT_NAME'] in ('iblrig_test_subject', 'test', 'test_subject'):
            log.warning('Not registering test subject to Alyx')
            return
        if not self.one or self.one.offline:
            return
        try:
            client = IBLRegistrationClient(self.one)
            ses, _ = client.register_session(self.paths.SESSION_FOLDER, register_reward=False)
        except Exception:
            log.error(traceback.format_exc())
            log.error('Could not register session to Alyx')
            return
        # add the water administration if there was water administered
        try:
            if self.session_info['TOTAL_WATER_DELIVERED']:
                wa = client.register_water_administration(
                    self.session_info.SUBJECT_NAME,
                    self.session_info['TOTAL_WATER_DELIVERED'] / 1000,
                    session=ses['url'][-36:],
                    water_type=self.task_params.get('REWARD_TYPE', None),
                )
                log.info(f"Water administered registered in Alyx database: {ses['subject']}, " f"{wa['water_administered']}mL")
        except Exception:
            log.error(traceback.format_exc())
            log.error('Could not register water administration to Alyx')
            return
        return ses

    def _execute_mixins_shared_function(self, pattern):
        """
        Loop over all methods of the class that start with pattern and execute them.

        Parameters
        ----------
        pattern : str
            'init_mixin', 'start_mixin', 'stop_mixin', or 'cleanup_mixin'
        """
        method_names = [method for method in dir(self) if method.startswith(pattern)]
        methods = [getattr(self, method) for method in method_names if inspect.ismethod(getattr(self, method))]
        for meth in methods:
            meth()

    @property
    def time_elapsed(self):
        return datetime.datetime.now() - self.init_datetime

    def mock(self):
        self.is_mock = True

    def create_session(self):
        """
        Create the session path and save json parameters in the task collection folder.

        This will also create the protocol folder.
        """
        self.paths['TASK_PARAMETERS_FILE'] = self.save_task_parameters_to_json_file()
        # enable file logging
        logfile = self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_ibl_log.info-acquisition.log')
        self._setup_loggers(level=self._logger.level, file=logfile)
        # copy the acquisition stub to the remote session folder
        sc = BehaviorCopier(self.paths.SESSION_FOLDER, remote_subjects_folder=self.paths['REMOTE_SUBJECT_FOLDER'])
        sc.initialize_experiment(self.experiment_description, overwrite=False)
        self.register_to_alyx()

    def run(self):
        """
        Common pre-run instructions for all tasks.

        Defines sigint handler for a graceful exit.
        """
        # here we make sure we connect to the hardware before writing the session to disk
        # this prevents from incrementing endlessly the session number if the hardware fails to connect
        self.start_hardware()
        self.create_session()
        # When not running the first chained protocol, we can skip the weighing dialog
        first_protocol = int(self.paths.SESSION_RAW_DATA_FOLDER.name.split('_')[-1]) == 0
        if self.session_info.SUBJECT_WEIGHT is None and self.interactive and first_protocol:
            self.session_info.SUBJECT_WEIGHT = graph.numinput(
                'Subject weighing (gr)', f'{self.session_info.SUBJECT_NAME} weight (gr):', nullable=False
            )

        def sigint_handler(*args, **kwargs):
            # create a signal handler for a graceful exit: create a stop flag in the session folder
            self.paths.SESSION_FOLDER.joinpath('.stop').touch()
            log.critical('SIGINT signal detected, will exit at the end of the trial')

        # if upon starting there is a flag just remove it, this is to prevent killing a session in the egg
        if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
            self.paths.SESSION_FOLDER.joinpath('.stop').unlink()

        signal.signal(signal.SIGINT, sigint_handler)
        self._run()  # runs the specific task logic i.e. trial loop etc...
        # post task instructions
        log.critical('Graceful exit')
        log.info(f'Session {self.paths.SESSION_RAW_DATA_FOLDER}')
        self.session_info.SESSION_END_TIME = datetime.datetime.now().isoformat()
        if self.interactive and not self.wizard:
            self.session_info.POOP_COUNT = graph.numinput(
                'Poop count', f'{self.session_info.SUBJECT_NAME} droppings count:', nullable=True, askint=True
            )
        self.save_task_parameters_to_json_file()
        self.register_to_alyx()
        self._execute_mixins_shared_function('stop_mixin')
        self._execute_mixins_shared_function('cleanup_mixin')

    @abstractmethod
    def start_hardware(self):
        """
        Start the hardware.

        This method doesn't explicitly start the mixins as the order has to be defined in the child classes.
        This needs to be implemented in the child classes, and should start and connect to all hardware pieces.
        """
        ...

    @abstractmethod
    def _run(self): ...

    @staticmethod
    def extra_parser():
        """
        Specify extra kwargs arguments to expose to the user prior running the task.

        Make sure you instantiate the parser.

        Returns
        -------
        argparse.ArgumentParser
            The extra parser instance.
        """
        parser = argparse.ArgumentParser(add_help=False)
        return parser

    @staticmethod
    def get_settings_model() -> type[BaseSettings]:
        config = SettingsConfigDict(cli_parse_args=True)
        return create_model('Test', __base__=BaseSettings, __cls_kwargs__={'cli_parse_args': True})

    @classmethod
    def get_settings_dict(cls) -> dict[str, Any]:
        return cls.get_settings_model()().model_dump()


# this class gets called to get the path constructor utility to predict the session path
class EmptySession(BaseSession):
    protocol_name = 'empty'

    def _run(self):
        pass

    def start_hardware(self):
        pass


class OSCClient(udp_client.SimpleUDPClient):
    """
    Handles communication to Bonsai using a UDP Client
    OSC channels:
        USED:
        /t  -> (int)    trial number current
        /p  -> (int)    position of stimulus init for current trial
        /h  -> (float)  phase of gabor for current trial
        /c  -> (float)  contrast of stimulus for current trial
        /f  -> (float)  frequency of gabor patch for current trial
        /a  -> (float)  angle of gabor patch for current trial
        /g  -> (float)  gain of RE to visual stim displacement
        /s  -> (float)  sigma of the 2D gaussian of gabor
        /e  -> (int)    events transitions  USED BY SOFTCODE HANDLER FUNC
        /r  -> (int)    whether to reverse the side contingencies (0, 1)
    """

    OSC_PROTOCOL = {
        'trial_num': dict(mess='/t', type=int),
        'position': dict(mess='/p', type=int),
        'stim_phase': dict(mess='/h', type=float),
        'contrast': dict(mess='/c', type=float),
        'stim_freq': dict(mess='/f', type=float),
        'stim_angle': dict(mess='/a', type=float),
        'stim_gain': dict(mess='/g', type=float),
        'stim_sigma': dict(mess='/s', type=float),
        # 'stim_reverse': dict(mess='/r', type=int),  # this is not handled by Bonsai
    }

    def __init__(self, port, ip='127.0.0.1'):
        super().__init__(ip, port)

    def __del__(self):
        self._sock.close()

    def send2bonsai(self, **kwargs):
        """
        :param see list of keys in OSC_PROTOCOL
        :example: client.send2bonsai(trial_num=6, sim_freq=50)
        :return:
        """
        for k in kwargs:
            if k in self.OSC_PROTOCOL:
                # need to convert basic numpy types to low-level python types for
                # punch card generation OSC module, I might as well have written C code
                value = kwargs[k].item() if isinstance(kwargs[k], np.generic) else kwargs[k]
                self.send_message(self.OSC_PROTOCOL[k]['mess'], self.OSC_PROTOCOL[k]['type'](value))

    def exit(self):
        self.send_message('/x', 1)


class BonsaiRecordingMixin(BaseSession):
    config: dict

    def init_mixin_bonsai_recordings(self, *args, **kwargs):
        self.bonsai_camera = Bunch({'udp_client': OSCClient(port=7111)})
        self.bonsai_microphone = Bunch({'udp_client': OSCClient(port=7112)})
        self.config = None  # the name of the configuration to run

    def stop_mixin_bonsai_recordings(self):
        log.info('Stopping Bonsai recordings')
        self.bonsai_camera.udp_client.exit()
        self.bonsai_microphone.udp_client.exit()

    def start_mixin_bonsai_microphone(self):
        if not self.config:
            # Use the first key in the device_cameras map
            self.config = next((k for k in self.hardware_settings.device_cameras), None)
        # The camera workflow on the behaviour computer already contains the microphone recording
        # so the device camera workflow and the microphone one are exclusive
        if self.config:
            return  # Camera workflow defined; so no need to separately start microphone.
        if not self.task_params.RECORD_SOUND:
            return  # Sound should not be recorded
        workflow_file = self.paths.IBLRIG_FOLDER.joinpath(*self.hardware_settings.device_microphone['BONSAI_WORKFLOW'].parts)
        parameters = {
            'FileNameMic': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_micData.raw.wav'),
            'RecordSound': self.task_params.RECORD_SOUND,
        }
        call_bonsai(workflow_file, parameters, wait=False, editor=False)
        log.info('Bonsai microphone recording module loaded: OK')

    @staticmethod
    def _camera_mixin_bonsai_get_workflow_file(cameras: dict | None, name: str) -> Path | None:
        """
        Returns the bonsai workflow file for the cameras from the hardware_settings.yaml file.

        Parameters
        ----------
        cameras : dict
            The hardware settings configuration.
        name : {'setup', 'recording'} str
            The workflow type.

        Returns
        -------
        Path
            The workflow path.
        """
        if cameras is None:
            return None
        return cameras['BONSAI_WORKFLOW'][name]

    def start_mixin_bonsai_cameras(self):
        """
        Prepare the cameras.

        Starts the pipeline that aligns the camera focus with the desired borders of rig features.
        The actual triggering of the cameras is done in the trigger_bonsai_cameras method.
        """
        if not self.config:
            # Use the first key in the device_cameras map
            try:
                self.config = next(k for k in self.hardware_settings.device_cameras)
            except StopIteration:
                return
        configuration = self.hardware_settings.device_cameras[self.config]
        if (workflow_file := self._camera_mixin_bonsai_get_workflow_file(configuration, 'setup')) is None:
            return

        # enable trigger of cameras (so Bonsai can disable it again ... sigh)
        if PYSPIN_AVAILABLE:
            from iblrig.video_pyspin import enable_camera_trigger

            enable_camera_trigger(True)

        call_bonsai(workflow_file, wait=True)  # TODO Parameterize using configuration cameras
        log.info('Bonsai cameras setup module loaded: OK')

    def trigger_bonsai_cameras(self):
        if not self.config:
            # Use the first key in the device_cameras map
            try:
                self.config = next(k for k in self.hardware_settings.device_cameras)
            except StopIteration:
                return
        configuration = self.hardware_settings.device_cameras[self.config]
        if set(configuration.keys()) != {'BONSAI_WORKFLOW', 'left'}:
            raise NotImplementedError
        workflow_file = self._camera_mixin_bonsai_get_workflow_file(configuration, 'recording')
        if workflow_file is None:
            return
        iblrig.path_helper.create_bonsai_layout_from_template(workflow_file)
        # FIXME Use parameters in configuration map
        parameters = {
            'FileNameLeft': self.paths.SESSION_FOLDER.joinpath('raw_video_data', '_iblrig_leftCamera.raw.avi'),
            'FileNameLeftData': self.paths.SESSION_FOLDER.joinpath('raw_video_data', '_iblrig_leftCamera.frameData.bin'),
            'FileNameMic': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_micData.raw.wav'),
            'RecordSound': self.task_params.RECORD_SOUND,
        }
        call_bonsai(workflow_file, parameters, wait=False, editor=False)
        log.info('Bonsai camera recording process started')


class BonsaiVisualStimulusMixin(BaseSession):
    def init_mixin_bonsai_visual_stimulus(self, *args, **kwargs):
        # camera 7111, microphone 7112
        self.bonsai_visual_udp_client = OSCClient(port=7110)

    def start_mixin_bonsai_visual_stimulus(self):
        self.choice_world_visual_stimulus()

    def stop_mixin_bonsai_visual_stimulus(self):
        log.info('Stopping Bonsai visual stimulus')
        self.bonsai_visual_udp_client.exit()

    def send_trial_info_to_bonsai(self):
        """
        Send the trial information to Bonsai via UDP.

        The OSC protocol is documented in iblrig.base_tasks.BonsaiVisualStimulusMixin
        """
        bonsai_dict = {
            k: self.trials_table[k][self.trial_num]
            for k in self.bonsai_visual_udp_client.OSC_PROTOCOL
            if k in self.trials_table.columns
        }

        # reverse wheel contingency: if stim_reverse is True we invert stim_gain
        if self.trials_table.get('stim_reverse', {}).get(self.trial_num, False):
            bonsai_dict['stim_gain'] = -bonsai_dict['stim_gain']

        self.bonsai_visual_udp_client.send2bonsai(**bonsai_dict)
        log.debug(bonsai_dict)

    def run_passive_visual_stim(self, map_time='00:05:00', rate=0.1, sa_time='00:05:00'):
        workflow_file = self.paths.VISUAL_STIM_FOLDER.joinpath('passiveChoiceWorld', 'passiveChoiceWorld_passive.bonsai')
        file_output_rfm = self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_RFMapStim.raw.bin')
        parameters = {
            'Stim.DisplayIndex': self.hardware_settings.device_screen['DISPLAY_IDX'],
            'Stim.SpontaneousActivity0.DueTime': sa_time,
            'Stim.ReceptiveFieldMappingStim.FileNameRFMapStim': file_output_rfm,
            'Stim.ReceptiveFieldMappingStim.MappingTime': map_time,
            'Stim.ReceptiveFieldMappingStim.Rate': rate,
        }
        map_seconds = pd.to_timedelta(map_time).seconds
        sa_seconds = pd.to_timedelta(sa_time).seconds
        log.info(f'Starting spontaneous activity ({sa_seconds} s) and RF mapping stims ({map_seconds} s)')
        s = call_bonsai(workflow_file, parameters, editor=False)
        log.info('Spontaneous activity and RF mapping stims finished')
        return s

    def choice_world_visual_stimulus(self):
        if self.task_params.VISUAL_STIMULUS is None:
            return
        workflow_file = self.paths.VISUAL_STIM_FOLDER.joinpath(self.task_params.VISUAL_STIMULUS)
        parameters = {
            'Stim.DisplayIndex': self.hardware_settings.device_screen['DISPLAY_IDX'],
            'Stim.FileNameStimPositionScreen': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_stimPositionScreen.raw.csv'),
            'Stim.FileNameSyncSquareUpdate': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_syncSquareUpdate.raw.csv'),
            'Stim.FileNamePositions': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_encoderPositions.raw.ssv'),
            'Stim.FileNameEvents': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_encoderEvents.raw.ssv'),
            'Stim.FileNameTrialInfo': self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_encoderTrialInfo.raw.ssv'),
            'Stim.REPortName': self.hardware_settings.device_rotary_encoder['COM_ROTARY_ENCODER'],
            'Stim.sync_x': self.task_params.SYNC_SQUARE_X,
            'Stim.sync_y': self.task_params.SYNC_SQUARE_Y,
            'Stim.TranslationZ': -self.task_params.STIM_TRANSLATION_Z,  # MINUS!!
        }
        call_bonsai(workflow_file, parameters, wait=False, editor=self.task_params.BONSAI_EDITOR, bootstrap=False)
        log.info('Bonsai visual stimulus module loaded: OK')


class BpodMixin(BaseSession):
    def _raise_on_undefined_softcode_handler(self, byte: int):
        raise ValueError(f'No handler defined for softcode #{byte}')

    def softcode_dictionary(self) -> OrderedDict[int, Callable]:
        """
        Returns a softcode handler dict where each key corresponds to the softcode and each value to the
        function to be called.

        This needs to be wrapped this way because
            1) we want to be able to inherit this and dynamically add softcode to the dictionry
            2) we need to provide the Task object (self) at run time to have the functions with static args
        This is tricky as it is unclear if the task object is a copy or a reference when passed here.


        Returns
        -------
        OrderedDict[int, Callable]
            Softcode dictionary
        """
        softcode_dict = OrderedDict(
            {
                SOFTCODE.STOP_SOUND: self.sound['sd'].stop,
                SOFTCODE.PLAY_TONE: lambda: self.sound['sd'].play(self.sound['GO_TONE'], self.sound['samplerate']),
                SOFTCODE.PLAY_NOISE: lambda: self.sound['sd'].play(self.sound['WHITE_NOISE'], self.sound['samplerate']),
                SOFTCODE.TRIGGER_CAMERA: getattr(
                    self, 'trigger_bonsai_cameras', lambda: self._raise_on_undefined_softcode_handler(SOFTCODE.TRIGGER_CAMERA)
                ),
            }
        )
        return softcode_dict

    def init_mixin_bpod(self, *args, **kwargs):
        self.bpod = Bpod()

    def stop_mixin_bpod(self):
        self.bpod.close()

    def start_mixin_bpod(self):
        if self.hardware_settings['device_bpod']['COM_BPOD'] is None:
            raise ValueError(
                'The value for device_bpod:COM_BPOD in '
                'settings/hardware_settings.yaml is null. Please '
                'provide a valid port name.'
            )
        disabled_ports = [x - 1 for x in self.hardware_settings['device_bpod']['DISABLE_BEHAVIOR_INPUT_PORTS']]
        self.bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'], disable_behavior_ports=disabled_ports)
        self.bpod.define_rotary_encoder_actions()
        self.bpod.set_status_led(False)
        assert self.bpod.is_connected
        log.info('Bpod hardware module loaded: OK')
        # make the bpod send spacer signals to the main sync clock for protocol discovery
        self.send_spacers()

    def send_spacers(self):
        log.info('Starting task by sending a spacer signal on BNC1')
        sma = StateMachine(self.bpod)
        Spacer().add_spacer_states(sma, next_state='exit')
        self.bpod.send_state_machine(sma)
        self.bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
        return self.bpod.session.current_trial.export()


class Frame2TTLMixin(BaseSession):
    """Frame 2 TTL interface for state machine."""

    def init_mixin_frame2ttl(self, *args, **kwargs):
        pass

    def start_mixin_frame2ttl(self):
        # todo assert calibration
        if self.hardware_settings['device_frame2ttl']['COM_F2TTL'] is None:
            raise ValueError(
                'The value for device_frame2ttl:COM_F2TTL in '
                'settings/hardware_settings.yaml is null. Please '
                'provide a valid port name.'
            )
        Frame2TTL(
            port=self.hardware_settings['device_frame2ttl']['COM_F2TTL'],
            threshold_dark=self.hardware_settings['device_frame2ttl']['F2TTL_DARK_THRESH'],
            threshold_light=self.hardware_settings['device_frame2ttl']['F2TTL_LIGHT_THRESH'],
        ).close()
        log.info('Frame2TTL: Thresholds set.')


class RotaryEncoderMixin(BaseSession):
    """Rotary encoder interface for state machine."""

    def init_mixin_rotary_encoder(self, *args, **kwargs):
        self.device_rotary_encoder = MyRotaryEncoder(
            all_thresholds=self.task_params.STIM_POSITIONS + self.task_params.QUIESCENCE_THRESHOLDS,
            gain=self.task_params.STIM_GAIN,
            com=self.hardware_settings.device_rotary_encoder['COM_ROTARY_ENCODER'],
            connect=False,
        )

    def start_mixin_rotary_encoder(self):
        if self.hardware_settings['device_rotary_encoder']['COM_ROTARY_ENCODER'] is None:
            raise ValueError(
                'The value for device_rotary_encoder:COM_ROTARY_ENCODER in '
                'settings/hardware_settings.yaml is null. Please '
                'provide a valid port name.'
            )
        try:
            self.device_rotary_encoder.connect()
        except serial.serialutil.SerialException as e:
            raise serial.serialutil.SerialException(
                f'The rotary encoder COM port {self.device_rotary_encoder.RE_PORT} is already in use. This is usually'
                f' due to a Bonsai process currently running on the computer. Make sure all Bonsai windows are'
                f' closed prior to running the task'
            ) from e
        except Exception as e:
            raise Exception(
                "The rotary encoder couldn't connect. If the bpod is glowing in green,"
                'disconnect and reconnect bpod from the computer'
            ) from e
        log.info('Rotary encoder module loaded: OK')


class ValveMixin(BaseSession, HasBpod):
    def init_mixin_valve(self: object):
        self.valve = Valve(self.hardware_settings.device_valve)

    def start_mixin_valve(self):
        # assert that valve has been calibrated
        assert self.valve.is_calibrated, """VALVE IS NOT CALIBRATED - PLEASE CALIBRATE THE VALVE"""

        # regardless of the calibration method, the reward valve time has to be lower than 1 second
        assert self.compute_reward_time(amount_ul=1.5) < 1, """VALVE IS NOT PROPERLY CALIBRATED - PLEASE RECALIBRATE"""
        log.info('Water valve module loaded: OK')

    def compute_reward_time(self, amount_ul: float | None = None) -> float:
        """
        Converts the valve opening time from a given volume.

        Parameters
        ----------
        amount_ul : float, optional
            The volume of liquid (μl) to be dispensed from the valve. Defaults to task_params.REWARD_AMOUNT_UL.

        Returns
        -------
        float
            Valve opening time in seconds.
        """
        amount_ul = self.task_params.REWARD_AMOUNT_UL if amount_ul is None else amount_ul
        return self.valve.values.ul2ms(amount_ul) / 1e3

    def valve_open(self, reward_valve_time):
        """
        Open the reward valve for a given amount of time and return bpod data.

        Parameters
        ----------
        reward_valve_time : float
            Amount of time in seconds to open the reward valve.
        """
        sma = StateMachine(self.bpod)
        sma.add_state(
            state_name='valve_open',
            state_timer=reward_valve_time,
            output_actions=[('Valve1', 255), ('BNC1', 255)],  # To FPGA
            state_change_conditions={'Tup': 'exit'},
        )
        self.bpod.send_state_machine(sma)
        self.bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
        return self.bpod.session.current_trial.export()


class SoundMixin(BaseSession, HasBpod):
    """Sound interface methods for state machine."""

    def init_mixin_sound(self):
        self.sound = Bunch({'GO_TONE': None, 'WHITE_NOISE': None})
        sound_output = self.hardware_settings.device_sound['OUTPUT']

        # additional gain factor for bringing the different combinations of sound-cards and amps to the same output level
        # TODO: this needs proper calibration and refactoring
        if self.hardware_settings.device_sound.OUTPUT == 'hifi' and self.hardware_settings.device_sound.AMP_TYPE == 'AMP2X15':
            amp_gain_factor = 0.25
        else:
            amp_gain_factor = 1.0
        self.task_params.GO_TONE_AMPLITUDE *= amp_gain_factor
        self.task_params.WHITE_NOISE_AMPLITUDE *= amp_gain_factor

        # sound device sd is actually the module soundevice imported above.
        # not sure how this plays out when referenced outside of this python file
        self.sound['sd'], self.sound['samplerate'], self.sound['channels'] = sound_device_factory(output=sound_output)
        # Create sounds and output actions of state machine
        self.sound['GO_TONE'] = iblrig.sound.make_sound(
            rate=self.sound['samplerate'],
            frequency=self.task_params.GO_TONE_FREQUENCY,
            duration=self.task_params.GO_TONE_DURATION,
            amplitude=self.task_params.GO_TONE_AMPLITUDE * amp_gain_factor,
            fade=0.01,
            chans=self.sound['channels'],
        )
        self.sound['WHITE_NOISE'] = iblrig.sound.make_sound(
            rate=self.sound['samplerate'],
            frequency=-1,
            duration=self.task_params.WHITE_NOISE_DURATION,
            amplitude=self.task_params.WHITE_NOISE_AMPLITUDE * amp_gain_factor,
            fade=0.01,
            chans=self.sound['channels'],
        )

    def start_mixin_sound(self):
        """
        Depends on bpod mixin start for hard sound card
        :return:
        """
        assert self.bpod.is_connected, 'The sound mixin depends on the bpod mixin being connected'
        # SoundCard config params
        match self.hardware_settings.device_sound['OUTPUT']:
            case 'harp':
                assert self.bpod.sound_card is not None, 'No harp sound-card connected to Bpod'
                sound.configure_sound_card(
                    sounds=[self.sound.GO_TONE, self.sound.WHITE_NOISE],
                    indexes=[self.task_params.GO_TONE_IDX, self.task_params.WHITE_NOISE_IDX],
                    sample_rate=self.sound['samplerate'],
                )
                self.bpod.define_harp_sounds_actions(
                    module=self.bpod.sound_card,
                    go_tone_index=self.task_params.GO_TONE_IDX,
                    noise_index=self.task_params.WHITE_NOISE_IDX,
                )
            case 'hifi':
                module = self.bpod.get_module('^HiFi')
                assert module is not None, 'No HiFi module connected to Bpod'
                assert self.hardware_settings.device_sound.COM_SOUND is not None
                hifi = HiFi(port=self.hardware_settings.device_sound.COM_SOUND, sampling_rate_hz=self.sound['samplerate'])
                hifi.load(index=self.task_params.GO_TONE_IDX, data=self.sound.GO_TONE)
                hifi.load(index=self.task_params.WHITE_NOISE_IDX, data=self.sound.WHITE_NOISE)
                hifi.push()
                hifi.close()
                self.bpod.define_harp_sounds_actions(
                    module=module,
                    go_tone_index=self.task_params.GO_TONE_IDX,
                    noise_index=self.task_params.WHITE_NOISE_IDX,
                )
            case _:
                self.bpod.define_xonar_sounds_actions()
        log.info(f"Sound module loaded: OK: {self.hardware_settings.device_sound['OUTPUT']}")

    def sound_play_noise(self, state_timer=0.510, state_name='play_noise'):
        """
        Play the noise sound for the error feedback using bpod state machine.
        :return: bpod current trial export
        """
        return self._sound_play(state_name=state_name, output_actions=[self.bpod.actions.play_tone], state_timer=state_timer)

    def sound_play_tone(self, state_timer=0.102, state_name='play_tone'):
        """
        Play the ready tone beep using bpod state machine.
        :return: bpod current trial export
        """
        return self._sound_play(state_name=state_name, output_actions=[self.bpod.actions.play_tone], state_timer=state_timer)

    def _sound_play(self, state_timer=None, output_actions=None, state_name='play_sound'):
        """Plays a sound using bpod state machine.

        The sound must be defined in the init_mixin_sound method.
        """
        assert state_timer is not None, 'state_timer must be defined'
        assert output_actions is not None, 'output_actions must be defined'
        sma = StateMachine(self.bpod)
        sma.add_state(
            state_name=state_name,
            state_timer=state_timer,
            output_actions=[self.bpod.actions.play_tone],
            state_change_conditions={'BNC2Low': 'exit', 'Tup': 'exit'},
        )
        self.bpod.send_state_machine(sma)
        self.bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
        return self.bpod.session.current_trial.export()


class NetworkSession(BaseSession):
    """A mixin for communicating to auxiliary acquisition PC over a network."""

    remote_rigs = None
    """net.Auxiliaries: An auxiliary services object for communicating with remote devices."""
    exp_ref = None
    """dict: The experiment reference (i.e. subject, date, sequence) as returned by main remote service."""

    def __init__(self, *_, remote_rigs=None, **kwargs):
        """
        A mixin for communicating to auxiliary acquisition PC over a network.

        This should retrieve the services list, i.e. the list of available auxiliary rigs,
        and determine which is the main sync. The main sync is the rig that determines the
        experiment.

        The services list is in a yaml file somewhere, called 'remote_rigs.yaml' and should
        be a map of device name to URI. These are then selectable in the GUI and the URI of
        those selected are added to the experiment description.

        Subclasses should add their callbacks within init by calling :meth:`self.remote_rigs.services.assign_callback`.

        Parameters
        ----------
        remote_rigs : list, dict
            Either a list of remote device names (in which case URI is looked up from remote devices
            file), or a map of device name to URI.
        kwargs
            Optional args such as 'file_iblrig_settings' for defining location of remote data folder
            when loading remote devices file.
        """
        if isinstance(remote_rigs, list):
            # For now we flatten to list of remote rig names but could permit list of (name, URI) tuples
            remote_rigs = list(filter(None, flatten(remote_rigs)))
            all_remote_rigs = net.get_remote_devices(iblrig_settings=kwargs.get('iblrig_settings'))
            if not set(remote_rigs).issubset(all_remote_rigs.keys()):
                raise ValueError('Selected remote rigs not in remote rigs list')
            remote_rigs = {k: v for k, v in all_remote_rigs.items() if k in remote_rigs}
        # Load and connect to remote services
        self.connect(remote_rigs)
        self.exp_ref = {}
        try:
            super().__init__(**kwargs)
        except Exception as ex:
            self.cleanup_mixin_network()
            raise ex

    @property
    def one(self):
        """Return ONE instance.

        Unlike super class getter, this method will always instantiate ONE, allowing subclasses to update with an Alyx
        token from a remotely connected rig.  This instance is used for formatting the experiment reference string.

        Returns
        -------
        one.api.One
            An instance of ONE.
        """
        if super().one is None:
            self._one = OneAlyx(silent=True, mode='local')
        return self._one

    def connect(self, remote_rigs):
        """
        Connect to remote services.

        Instantiates the Communicator objects that establish connections with each remote device.
        This also creates the thread that uses asynchronous callbacks.

        Parameters
        ----------
        remote_rigs : dict
            A map of name to URI.
        """
        self.remote_rigs = net.Auxiliaries(remote_rigs or {})
        assert not remote_rigs or self.remote_rigs.is_connected
        # Handle termination event by graciously completing thread
        signal.signal(signal.SIGTERM, lambda sig, frame: self.cleanup_mixin_network())

    def _init_paths(self, append: bool = False):
        """
        Determine session paths.

        Unlike :meth:`BaseSession._init_paths`, this method determines the session number from the remote main sync if
        connected.

        Parameters
        ----------
        append : bool
            Iterate task collection within today's most recent session folder for the selected subject, instead of
            iterating session number.

        Returns
        -------
        iblutil.util.Bunch
            A bunch of paths.
        """
        if self.hardware_settings.MAIN_SYNC:
            return BaseSession._init_paths(self, append)
        # Check if we have rigs connected
        if not self.remote_rigs.is_connected:
            log.warning('No remote rigs; experiment reference may not match the main sync.')
            return BaseSession._init_paths(self, append)
        # Set paths in a similar way to the super class
        rig_computer_paths = iblrig.path_helper.get_local_and_remote_paths(
            local_path=self.iblrig_settings['iblrig_local_data_path'],
            remote_path=self.iblrig_settings['iblrig_remote_data_path'],
            lab=self.iblrig_settings['ALYX_LAB'],
            iblrig_settings=self.iblrig_settings,
        )
        paths = Bunch({'IBLRIG_FOLDER': BASE_PATH})
        paths.BONSAI = BONSAI_EXE
        paths.VISUAL_STIM_FOLDER = paths.IBLRIG_FOLDER.joinpath('visual_stim')
        paths.LOCAL_SUBJECT_FOLDER = rig_computer_paths['local_subjects_folder']
        paths.REMOTE_SUBJECT_FOLDER = rig_computer_paths['remote_subjects_folder']
        date_folder = paths.LOCAL_SUBJECT_FOLDER.joinpath(
            self.session_info.SUBJECT_NAME, self.session_info.SESSION_START_TIME[:10]
        )
        assert self.exp_ref
        paths.SESSION_FOLDER = date_folder / f'{self.exp_ref["sequence"]:03}'
        paths.TASK_COLLECTION = iblrig.path_helper.iterate_collection(paths.SESSION_FOLDER)
        if append == paths.TASK_COLLECTION.endswith('00'):
            raise ValueError(
                f'Append value incorrect. Either remove previous task collections from '
                f'{paths.SESSION_FOLDER}, or select append in GUI (--append arg in cli)'
            )

        paths.SESSION_RAW_DATA_FOLDER = paths.SESSION_FOLDER.joinpath(paths.TASK_COLLECTION)
        paths.DATA_FILE_PATH = paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable')
        paths.SETTINGS_FILE_PATH = paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        self.session_info.SESSION_NUMBER = int(paths.SESSION_FOLDER.name)
        return paths

    def run(self):
        """Run session and report exceptions to remote services."""
        self.start_mixin_network()
        try:
            return super().run()
        except Exception as e:
            # Communicate error to services
            if self.remote_rigs.is_connected:
                tb = e.__traceback__  # TODO maybe go one level down with tb_next?
                details = {
                    'error': e.__class__.__name__,  # exception name str
                    'message': str(e),  # error str
                    'traceback': traceback.format_exc(),  # stack str
                    'file': tb.tb_frame.f_code.co_filename,  # filename str
                    'line_no': (tb.tb_lineno, tb.tb_lasti),  # (int, int)
                }
                self.remote_rigs.push(ExpMessage.EXPINTERRUPT, details, wait=True)
                self.cleanup_mixin_network()
            raise e

    def communicate(self, message, *args, raise_on_exception=True):
        """
        Communicate message to remote services.

        This method is blocking and by default will raise if not all responses received in time.

        Parameters
        ----------
        message : iblutil.io.net.base.ExpMessage, str, int
            An experiment message to send to remote services.
        args
            One or more optional variables to send.
        raise_on_exception : bool
            If true, exceptions arising from message timeouts will be re-raised in main thread and
            services will be cleaned up. Only applies when wait is true.

        Returns
        -------
        Exception | dict
            If raise_on_exception is False, returns an exception if failed to receive all responses
            in time, otherwise a map of service name to response is returned.
        """
        r = self.remote_rigs.push(message, *args, wait=True)
        if isinstance(r, Exception):
            log.error('Error on %s network mixin: %s', message, r)
            if raise_on_exception:
                self.cleanup_mixin_network()
                raise r
        return r

    def get_exp_info(self):
        ref = self.exp_ref or None
        if isinstance(ref, dict) and self.one:
            ref = self.one.dict2ref(ref)
        is_main_sync = self.hardware_settings.get('MAIN_SYNC', False)
        info = net.ExpInfo(ref, is_main_sync, self.experiment_description, master=is_main_sync)
        return info.to_dict()

    def init_mixin_network(self):
        """Initialize remote services.

        This method sends an EXPINFO message to all services, expecting exactly one of the responses
        to contain main_sync: True, along with the experiment reference to use. It then sends an
        EXPINIT message to all services.
        """
        if not self.remote_rigs.is_connected:
            return
        # Determine experiment reference from main sync
        is_main_sync = self.hardware_settings.get('MAIN_SYNC', False)
        if is_main_sync:
            raise NotImplementedError
        assert self.one

        expinfo = self.get_exp_info() | {'subject': self.session_info['SUBJECT_NAME']}
        r = self.communicate('EXPINFO', 'CONNECTED', expinfo)
        assert sum(x[-1]['main_sync'] for x in r.values()) == 1, 'one main sync expected'
        main_rig_name, (status, info) = next((k, v) for k, v in r.items() if v[-1]['main_sync'])
        self.exp_ref = self.one.ref2dict(info['exp_ref']) if isinstance(info['exp_ref'], str) else info['exp_ref']
        if self.exp_ref['subject'] != self.session_info['SUBJECT_NAME']:
            log.error(
                'Running task for "%s" but main sync returned exp ref for "%s".',
                self.session_info['SUBJECT_NAME'],
                self.exp_ref['subject'],
            )
            raise ValueError("Subject name doesn't match remote session on " + main_rig_name)
        if str(self.exp_ref['date']) != self.session_info['SESSION_START_TIME'][:10]:
            raise RuntimeError(
                f'Session dates do not match between this rig and {main_rig_name}. \n'
                f'Running past or future sessions not currently supported. \n'
                f'Please check the system date time settings on each rig.'
            )

        # exp_ref = ConversionMixin.path2ref(self.paths['SESSION_FOLDER'], as_dict=False)
        exp_ref = self.one.dict2ref(self.exp_ref)
        self.communicate('EXPINIT', {'exp_ref': exp_ref})

    def start_mixin_network(self):
        """Start remote services.

        This method sends an EXPSTART message to all services, along with an exp_ref string.
        Responses are required but ignored.
        """
        if not self.remote_rigs.is_connected:
            return
        self.communicate('EXPSTART', self.exp_ref)

    def stop_mixin_network(self):
        """Start remote services.

        This method sends an EXPEND message to all services. Responses are required but ignored.
        """
        if not self.remote_rigs.is_connected:
            return
        self.communicate('EXPEND')

    def cleanup_mixin_network(self):
        """Clean up services."""
        self.remote_rigs.close()
        if self.remote_rigs.is_connected:
            log.warning('Failed to properly clean up network mixin')


class SpontaneousSession(BaseSession):
    """
    A Spontaneous task doesn't have trials, it just runs until the user stops it.

    It is used to get extraction structure for data streams
    """

    def __init__(self, duration_secs=None, **kwargs):
        super().__init__(**kwargs)
        self.duration_secs = duration_secs

    def start_hardware(self):
        pass  # no mixin here, life is but a dream

    def _run(self):
        """Run the task with the actual state machine."""
        log.info('Starting spontaneous acquisition')
        while True:
            time.sleep(1.5)
            if self.duration_secs is not None and self.time_elapsed.seconds > self.duration_secs:
                break
            if self.paths.SESSION_FOLDER.joinpath('.stop').exists():
                self.paths.SESSION_FOLDER.joinpath('.stop').unlink()
                break
