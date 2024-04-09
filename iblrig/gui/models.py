import dataclasses
from collections import OrderedDict
import importlib.util
import logging
from pathlib import Path
import sys

from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread
from requests import HTTPError

import iblrig.hardware_validation
import iblrig.path_helper
import iblrig_tasks
from iblrig.choiceworld import get_subject_training_info
from iblrig.base_tasks import EmptySession, ValveMixin
from iblrig.hardware import Bpod
from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings, RigSettings
from one.webclient import AlyxClient
from pybpodapi.exceptions.bpod_error import BpodErrorException

try:
    import iblrig_custom_tasks
    CUSTOM_TASKS = True
except ImportError:
    CUSTOM_TASKS = False
    pass

PROCEDURES = [
    'Behavior training/tasks',
    'Ephys recording with acute probe(s)',
    'Ephys recording with chronic probe(s)',
    'Fiber photometry',
    'handling_habituation',
    'Imaging',
]

PROJECTS = ['ibl_neuropixel_brainwide_01', 'practice']

log = logging.getLogger(__name__)


class SubjectDetailsWorker(QThread):
    subject_name: str | None = None
    result: tuple[dict, dict] | None = None

    def __init__(self, subject_name):
        super().__init__()
        self.subject_name = subject_name

    def run(self):
        self.result = get_subject_training_info(self.subject_name)


@dataclasses.dataclass
class RigWizardModel:
    alyx: AlyxClient | None = None
    procedures: list | None = None
    projects: list | None = None
    task_name: str | None = None
    user: str | None = None
    subject: str | None = None
    session_folder: Path | None = None
    test_subject_name = 'test_subject'
    subject_details_worker = None
    subject_details: tuple | None = None
    free_reward_time: float | None = None
    file_iblrig_settings: Path | str | None = None
    file_hardware_settings: Path | str | None = None

    def __post_init__(self):
        self.iblrig_settings: RigSettings = load_pydantic_yaml(RigSettings, filename=self.file_iblrig_settings, do_raise=True)
        self.hardware_settings: HardwareSettings = load_pydantic_yaml(
            HardwareSettings, filename=self.file_hardware_settings, do_raise=True
        )

        # calculate free reward time
        class FakeSession(EmptySession, ValveMixin):
            pass

        fake_session = FakeSession(
            subject='gui_init_subject',
            file_hardware_settings=self.file_hardware_settings,
            file_iblrig_settings=self.file_iblrig_settings,
        )
        fake_session.task_params.update({'AUTOMATIC_CALIBRATION': True, 'REWARD_AMOUNT_UL': 10})
        fake_session.init_mixin_valve()
        self.free_reward_time = fake_session.compute_reward_time(self.hardware_settings.device_valve.FREE_REWARD_VOLUME_UL)

        if self.iblrig_settings.ALYX_URL is not None:
            self.alyx = AlyxClient(base_url=str(self.iblrig_settings.ALYX_URL), silent=True)

        self.all_users = [self.iblrig_settings['ALYX_USER']] if self.iblrig_settings['ALYX_USER'] else []
        self.all_procedures = sorted(PROCEDURES)
        self.all_projects = sorted(PROJECTS)

        # for the tasks, we build a dictionary that contains the task name as key and the path to task.py as value
        tasks = sorted([p for p in Path(iblrig_tasks.__file__).parent.rglob('task.py')])
        if CUSTOM_TASKS:
            tasks.extend(sorted([p for p in Path(iblrig_custom_tasks.__file__).parent.rglob('task.py')]))
        self.all_tasks = OrderedDict({p.parts[-2]: p for p in tasks})

        # get the subjects from iterating over folders in the the iblrig data path
        if self.iblrig_settings['iblrig_local_data_path'] is None:
            self.all_subjects = [self.test_subject_name]
        else:
            folder_subjects = Path(self.iblrig_settings['iblrig_local_data_path']).joinpath(
                self.iblrig_settings['ALYX_LAB'], 'Subjects'
            )
            self.all_subjects = [self.test_subject_name] + sorted(
                [f.name for f in folder_subjects.glob('*') if f.is_dir() and f.name != self.test_subject_name]
            )

    def get_task_extra_parser(self, task_name=None):
        """
        Get the extra kwargs from the task, by importing the task and parsing the extra_parser static method
        This parser will give us a list of arguments and their types so we can build a custom dialog for this task
        :return:
        """
        assert task_name
        spec = importlib.util.spec_from_file_location('task', self.all_tasks[task_name])
        task = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = task
        spec.loader.exec_module(task)
        return task.Session.extra_parser()

    def login(
        self,
        username: str,
        password: str | None = None,
        do_cache: bool = False,
        alyx_client: AlyxClient | None = None,
        gui: bool = False,
    ) -> bool:
        # Use predefined AlyxClient for testing purposes:
        if alyx_client is not None:
            self.alyx = alyx_client

        # Alternatively, try to log in:
        else:
            try:
                self.alyx.authenticate(username, password, do_cache, force=password is not None)
                if self.alyx.is_logged_in and self.alyx.user == username:
                    self.user = self.alyx.user
                    log.info(f'Logged into {self.alyx.base_url} as {self.alyx.user}')
                else:
                    return False
            except HTTPError as e:
                if e.errno == 400 and any(x in e.response.text for x in ('credentials', 'required')):
                    log.error(e.filename)
                    return False
                else:
                    raise e

        # since we are connecting to Alyx, validate some parameters to ensure a smooth extraction
        result = iblrig.hardware_validation.ValidateAlyxLabLocation(
            iblrig_settings=self.iblrig_settings,
            hardware_settings=self.hardware_settings,
        ).run(self.alyx)
        if result.status == 'FAIL' and gui:
            QtWidgets.QMessageBox().critical(None, 'Error', f'{result.message}\n\n{result.solution}')

        # get subjects from Alyx: this is the set of subjects that are alive and not stock in the lab defined in settings
        rest_subjects = self.alyx.rest('subjects', 'list', alive=True, stock=False, lab=self.iblrig_settings['ALYX_LAB'])
        self.all_subjects.remove(self.test_subject_name)
        self.all_subjects = [self.test_subject_name] + sorted(set(self.all_subjects + [s['nickname'] for s in rest_subjects]))
        # then get the projects that map to the current user
        rest_projects = self.alyx.rest('projects', 'list')
        projects = [p['name'] for p in rest_projects if (username in p['users'] or len(p['users']) == 0)]
        self.all_projects = sorted(set(projects + self.all_projects))
        return True

    def logout(self):
        if not self.alyx.is_logged_in or self.alyx.user is not self.user:
            return
        log.info(f'User {self.user} logged out')
        self.alyx.logout()
        self.user = None
        self.__post_init__()

    def free_reward(self):
        try:
            bpod = Bpod(
                self.hardware_settings['device_bpod']['COM_BPOD'],
                skip_initialization=True,
                disable_behavior_ports=[1, 2, 3],
            )
            bpod.pulse_valve(open_time_s=self.free_reward_time)
        except (OSError, BpodErrorException):
            log.error('Cannot find bpod - is it connected?')
            return

    def get_subject_details(self, subject):
        self.subject_details_worker = SubjectDetailsWorker(subject)
        self.subject_details_worker.finished.connect(self.process_subject_details)
        self.subject_details_worker.start()

    def process_subject_details(self):
        self.subject_details = SubjectDetailsWorker.result


@dataclasses.dataclass
class Trajectory():
    x: float | None = None  # um relative to Bregma, right is positive
    y: float | None = None  # um relative to Bregma, posterior is positive
    z: float | None = None  # um relative to Bregma, dorsal is positive
    phi: float | None = None  # azimuth from right 0 - 360 degrees
    theta: float | None = None  # polar angle from horizontal
    depth: float | None = None  # um
    roll: float = 0

    def __dict__(self):
        return dataclasses.asdict(self)

    def get_slice_type(self):
        """
        return the slice type from the azimuth angle phi
        If the trajectory model doesn't pass validation, return None
        :return:
        """
        if not self.validate():
            return
        if 45 < abs(self.phi - 180) <= 135:
            return 'coronal'
        else:
            return 'sagittal'

    def validate(self):
        """
        validate the trajectory values:
        -   None of the fields should be set to Null
        -   Z should be positive
        -   theta is an angle from 0 to 90 degrees
        -   phi is an angle from 0 to 360 degrees
        :return:
        """
        for k, v in dataclasses.asdict(self).items():
            if v is None:
                return False
        if self.z < 0:
            return False
        if not 0 <= self.theta <= 90:
            return False
        if not 0 <= self.phi <= 360:
            return False
        return True


class MicroManipulatorModel(RigWizardModel):
    trajectory: Trajectory | None = None

    def __init__(self):
        super().__init__()
        self.trajectory = Trajectory(**{
            'x': -1200.1, 'y': -4131.3, 'z': 901.1, 'phi': 270, 'theta': 15, 'depth': 3300.7, 'roll': 0})
        self.trajectories = {}
        self.pname = 'probe01'
