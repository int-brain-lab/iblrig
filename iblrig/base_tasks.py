"""
This module is intended to provide commonalities for all tasks.
It provides hardware mixins that can be used together with BaseSession to compose tasks
This module is exclusive of any task related logic
"""
import json

from pathlib import Path
from abc import ABC
import datetime
import inspect
import logging
import os
import serial
import subprocess
import yaml
import signal
import traceback

import numpy as np
import scipy.interpolate

from pythonosc import udp_client
from pybpodapi.protocol import StateMachine
from one.api import ONE

import iblrig
import iblrig.path_helper
from iblutil.util import Bunch
from iblrig.hardware import Bpod, MyRotaryEncoder, sound_device_factory
import iblrig.frame2TTL as frame2TTL
import iblrig.sound as sound
import iblrig.spacer
import iblrig.alyx

log = logging.getLogger("iblrig")

OSC_CLIENT_IP = "127.0.0.1"


class BaseSession(ABC):
    protocol_name = None
    base_parameters_file = None
    is_mock = False

    def __init__(self, task_parameter_file=None, hardware_settings=None, iblrig_settings=None,
                 one=None, interactive=True, subject=None, projects=None, procedures=None):
        """
        :param task_parameter_file:
        :param hardware_settings: name of the hardware file in the settings folder, or full file path
        :param iblrig_settings: name of the iblrig file in the settings folder, or full file path
        :param one: an instance of ONE if any
        :param interactive:
        :param subject:
        :param projects:
        :param procedures:
        :param fmake: (DEPRECATED) if True, only create the raw_behavior_data folder.
        """
        self.interactive = interactive
        self._one = one
        self.init_datetime = datetime.datetime.now()
        # Create the folder architecture and get the paths property updated
        # the template for this file is in settings/hardware_settings.yaml
        self.hardware_settings = iblrig.path_helper.load_settings_yaml(hardware_settings or 'hardware_settings.yaml')
        self.iblrig_settings = iblrig.path_helper.load_settings_yaml(iblrig_settings or 'iblrig_settings.yaml')
        # TODO Base collections on experiment description and remove 'fmake' param.
        # Load the tasks settings, from the task folder or override with the input argument
        task_parameter_file = task_parameter_file or Path(inspect.getfile(self.__class__)).parent.joinpath('task_parameters.yaml')
        self.task_params = Bunch({})
        # first loads the base parameters for a given task
        if self.base_parameters_file is not None and self.base_parameters_file.exists():
            with open(self.base_parameters_file) as fp:
                self.task_params = Bunch(yaml.safe_load(fp))
        # then updates the dictionary with the child task parameters
        if task_parameter_file.exists():
            with open(task_parameter_file) as fp:
                task_params = yaml.safe_load(fp)
            if task_params is not None:
                self.task_params.update(Bunch(task_params))
        self.session_info = Bunch({
            'NTRIALS_CORRECT': 0,
            'PROCEDURES': procedures,
            'PROJECTS': projects,
            'SESSION_START_TIME': self.init_datetime.isoformat(),
            'SESSION_END_TIME': None,
            'SESSION_NUMBER': 0,
            'SUBJECT_NAME': subject or self.pybpod_settings.PYBPOD_SUBJECTS[0],
            'SUBJECT_WEIGHT': None,
            'TOTAL_WATER_DELIVERED': 0,
        })

        root_data_path = Path(self.iblrig_settings['iblrig_local_data_path']) or Path.home().joinpath('iblrig_data')
        date_folder = root_data_path.joinpath(
            self.iblrig_settings['ALYX_LAB'] or '',
            'Subjects',
            self.session_info.SUBJECT_NAME,
            self.session_info.SESSION_START_TIME[:10],
        )
        numbers_folders = [int(f.name) for f in date_folder.rglob('*') if len(f.name) == 3 and f.name.isdigit()]
        self.session_info.SESSION_NUMBER = 1 if len(numbers_folders) == 0 else max(numbers_folders) + 1
        self.paths = Bunch({
            'SESSION_FOLDER': date_folder.joinpath(f"{self.session_info.SESSION_NUMBER:03d}"),
            'IBLRIG_FOLDER': Path(iblrig.__file__).parents[1],
        })
        self.paths.BONSAI = self.paths.IBLRIG_FOLDER.joinpath('Bonsai', 'Bonsai.exe')
        # Create the session folder, this is currently hard coded but should be changed for chained protocols
        self.paths.SESSION_RAW_DATA_FOLDER = self.paths.SESSION_FOLDER.joinpath('raw_behavior_data')
        self.paths.DATA_FILE_PATH = self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable')
        self.paths.VISUAL_STIM_FOLDER = self.paths.IBLRIG_FOLDER.joinpath('visual_stim')
        # Executes mixins init methods
        self._execute_mixins_shared_function('init_mixin')
        self.save_task_parameters_to_json_file()

    def _make_task_parameters_dict(self):
        """
        This makes the dictionary that will be saved to the settings json file for extraction
        :return:
        """
        output_dict = dict(self.task_params)  # Grab parameters from task_params session
        output_dict.update(dict(self.hardware_settings))  # Update dict with hardware settings from session
        output_dict.update(dict(self.session_info))  # Update dict with session_info (subject, procedure, projects)
        patch_dict = {  # Various values added to ease transition from iblrig v7 to v8, different home may be desired
            "IBLRIG_VERSION": iblrig.__version__,
            "PYBPOD_PROTOCOL": self.protocol_name,
            "ALYX_USER": self.iblrig_settings.ALYX_USER,
            'ALYX_LAB': self.iblrig_settings.ALYX_LAB,
        }
        output_dict.update(patch_dict)
        return output_dict

    def save_task_parameters_to_json_file(self) -> Path:
        """
        Given a session object, collects the various settings and parameters of the session and outputs them to a JSON file

        Returns
        -------
        Path to the resultant JSON file
        """
        output_dict = self._make_task_parameters_dict()
        # Output dict to json file
        json_file = self.paths.SESSION_FOLDER / "raw_behavior_data" / "_iblrig_taskSettings.raw.json"
        json_file.parent.mkdir(parents=True, exist_ok=True)
        with open(json_file, "w") as outfile:
            json.dump(output_dict, outfile, indent=4, sort_keys=True, default=str)  # converts datetime objects to string
        return json_file  # PosixPath

    @property
    def one(self):
        """
        One getter
        :return:
        """
        if self._one is None:
            if self.iblrig_settings['ALYX_URL'] is None:
                return
            info_str = f"alyx client with user name {self.iblrig_settings['ALYX_USER']} " + \
                       f"and url: {self.iblrig_settings['ALYX_URL']}"
            try:
                self._one = ONE(
                    base_url=self.iblrig_settings['ALYX_URL'],
                    username=self.iblrig_settings['ALYX_USER'],
                    mode='remote'
                )
                log.info("instantiated " + info_str)
            except Exception:
                log.error(traceback.format_exc())
                log.error("could not connect to " + info_str)
        return self._one

    def register_to_alyx(self):
        """
        Registers the session to Alyx.
        To make sure the registration is the same from the settings files and from the instantiated class
        we output the settings dictionary and register from this format directly.
        Alternatively, this function
        :return:
        """
        settings_dictionary = self._make_task_parameters_dict()
        try:
            iblrig.alyx.register_session(self.paths.SESSION_FOLDER, settings_dictionary, one=self.one)
        except Exception:
            log.error(traceback.format_exc())
            log.error("Could not register session to Alyx")

    def _execute_mixins_shared_function(self, pattern):
        method_names = [method for method in dir(self) if method.startswith(pattern)]
        methods = [getattr(self, method) for method in method_names if inspect.ismethod(getattr(self, method))]
        # todo add logging error catching with traceback
        for meth in methods:
            meth()

    def start(self):
        """
        Executes all start_mixin* methods
        """
        self._execute_mixins_shared_function('start_mixin')

    def stop(self):
        """
        Executes all stop_mixin* methods
        """
        self._execute_mixins_shared_function('stop_mixin')

    @property
    def time_elapsed(self):
        return datetime.datetime.now() - self.init_datetime

    def mock(self):
        self.is_mock = True

    def run(self):
        """
        Common pre-run instructions for all tasks: singint handler for a graceful exit
        And send spacers to the bpod
        :return:
        """
        def sigint_handler(*args, **kwargs):
            self.paths.SESSION_FOLDER.joinpath('.stop').touch()
            log.critical("SIGINT signal detected, will exit at the end of the trial")

        signal.signal(signal.SIGINT, sigint_handler)

        self.start()
        self.send_spacers()


class OSCClient(udp_client.SimpleUDPClient):
    """
    Handles communication to Bonsai using an UDP Client
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
        'stim_reverse': dict(mess='/r', type=int),
    }

    def __init__(self, port, ip="127.0.0.1"):
        super(OSCClient, self).__init__(ip, port)

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
        self.send_message("/x", 1)


class BonsaiRecordingMixin(object):

    def init_mixin_bonsai_recordings(self, *args, **kwargs):
        self.bonsai_camera = Bunch({
            'udp_client': OSCClient(port=7111)
        })
        self.bonsai_microphone = Bunch({
            'udp_client': OSCClient(port=7112)
        })

    def stop_mixin_bonsai_recordings(self):
        self.bonsai_camera.udp_client.exit()
        self.bonsai_microphone.udp_client.exit()

    def start_mixin_bonsai_microphone(self):
        # the camera workflow on the behaviour computer already contains the microphone recording
        # so the device camera workflow and the microphone one are exclusive
        if self.hardware_settings.device_camera['BONSAI_WORKFLOW'] is not None:
            return
        if not self.task_params.RECORD_SOUND:
            return
        workflow_file = self.paths.IBLRIG_FOLDER.joinpath(
            *self.hardware_settings.device_microphone['BONSAI_WORKFLOW'].split('/'))
        here = os.getcwd()
        os.chdir(workflow_file.parent)
        subprocess.Popen([
            str(self.paths.BONSAI),
            str(workflow_file),
            "--start",
            f"-p:FileNameMic={self.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_micData.raw.wav')}",
            f"-p:RecordSound={self.task_params.RECORD_SOUND}",
            "--no-boot"]
        )
        os.chdir(here)
        log.info("Bonsai microphone recording module loaded: OK")

    def start_mixin_bonsai_cameras(self):
        """
        This prepares the cameras by starting the pipeline that aligns the camera focus with the
        desired borders of rig features, the actual triggering of the  cameras is done in the trigger_bonsai_cameras method.
        """
        if self.hardware_settings.device_camera['BONSAI_WORKFLOW'] is None:
            return
        here = os.getcwd()
        bonsai_camera_file = self.paths.IBLRIG_FOLDER.joinpath('devices', 'camera_setup', 'setup_video.bonsai')
        os.chdir(str(bonsai_camera_file.parent))
        # this locks until Bonsai closes
        subprocess.call([str(self.paths.BONSAI), str(bonsai_camera_file), "--start-no-debug", "--no-boot"])
        os.chdir(here)
        log.info("Bonsai cameras setup module loaded: OK")

    def trigger_bonsai_cameras(self):
        if self.hardware_settings.device_camera['BONSAI_WORKFLOW'] is None:
            return
        workflow_file = self.paths.IBLRIG_FOLDER.joinpath(
            *self.hardware_settings.device_camera['BONSAI_WORKFLOW'].split('/'))
        here = os.getcwd()
        os.chdir(workflow_file.parent)
        subprocess.Popen([
            str(self.paths.BONSAI),
            str(workflow_file),
            "--start",
            f"-p:FileNameLeft={self.paths.SESSION_FOLDER / 'raw_video_data' / '_iblrig_leftCamera.raw.avi'}",
            f"-p:FileNameLeftData={self.paths.SESSION_FOLDER / 'raw_video_data' / '_iblrig_leftCamera.frameData.bin'}",
            f"-p:FileNameMic={self.paths.SESSION_FOLDER / 'raw_video_data' / '_iblrig_micData.raw.wav'}",
            f"-p:RecordSound={self.task_params.RECORD_SOUND}",
            "--no-boot",
        ])
        os.chdir(here)


class BonsaiVisualStimulusMixin(object):

    def init_mixin_bonsai_visual_stimulus(self, *args, **kwargs):
        self.bonsai_stimulus = Bunch({
            'udp_client': OSCClient(port=7110)  # camera 7111, microphone 7112
        })

    def start_mixin_bonsai_visual_stimulus(self):
        if self.task_params.VISUAL_STIMULUS is None:
            return
        # Run Bonsai workflow, switch to the folder containing the gnagnagna.bonsai viusal stimulus file

        visual_stim_file = self.paths.VISUAL_STIM_FOLDER.joinpath(self.task_params.VISUAL_STIMULUS)

        evt = "-p:Stim.FileNameEvents=" + os.path.join(
            self.paths.SESSION_RAW_DATA_FOLDER, "_iblrig_encoderEvents.raw.ssv"
        )
        pos = "-p:Stim.FileNamePositions=" + os.path.join(
            self.paths.SESSION_RAW_DATA_FOLDER, "_iblrig_encoderPositions.raw.ssv"
        )
        itr = "-p:Stim.FileNameTrialInfo=" + os.path.join(
            self.paths.SESSION_RAW_DATA_FOLDER, "_iblrig_encoderTrialInfo.raw.ssv"
        )
        screen_pos = "-p:Stim.FileNameStimPositionScreen=" + os.path.join(
            self.paths.SESSION_RAW_DATA_FOLDER, "_iblrig_stimPositionScreen.raw.csv"
        )
        sync_square = "-p:Stim.FileNameSyncSquareUpdate=" + os.path.join(
            self.paths.SESSION_RAW_DATA_FOLDER, "_iblrig_syncSquareUpdate.raw.csv"
        )

        com = "-p:Stim.REPortName=" + self.hardware_settings.device_rotary_encoder['COM_ROTARY_ENCODER']
        display_idx = "-p:Stim.DisplayIndex=" + str(self.hardware_settings.device_screen['DISPLAY_IDX'])
        sync_x = "-p:Stim.sync_x=" + str(self.task_params.SYNC_SQUARE_X)
        sync_y = "-p:Stim.sync_y=" + str(self.task_params.SYNC_SQUARE_Y)
        translationz = f"-p:Stim.TranslationZ=-{self.task_params.STIM_TRANSLATION_Z}"
        noboot = "--no-boot"
        editor = "--start" if self.task_params.BONSAI_EDITOR else "--no-editor"

        here = Path.cwd()
        os.chdir(visual_stim_file.parent)

        subprocess.Popen(
            [
                str(self.paths.BONSAI),
                visual_stim_file,
                editor,
                noboot,
                display_idx,
                screen_pos,
                sync_square,
                pos,
                evt,
                itr,
                com,
                sync_x,
                sync_y,
                translationz,
            ]
        )
        os.chdir(here)
        log.info("Bonsai visual stimulus module loaded: OK")


class BpodMixin(object):

    def init_mixin_bpod(self, *args, **kwargs):
        self.bpod = Bpod()

    def start_mixin_bpod(self):
        self.bpod = Bpod(self.hardware_settings['device_bpod']['COM_BPOD'])
        self.bpod.define_rotary_encoder_actions()

        def softcode_handler(code):
            """
             Soft codes should work with resasonable latency considering our limiting
             factor is the refresh rate of the screen which should be 16.667ms @ a framerate of 60Hz
             """
            if code == 0:
                self.stop_sound()
            elif code == 1:
                self.play_tone()
            elif code == 2:
                self.play_noise()
            elif code == 3:
                self.trigger_bonsai_cameras()
        self.bpod.softcode_handler_function = softcode_handler

        assert len(self.bpod.actions.keys()) == 6
        assert self.bpod.is_connected
        log.info("Bpod hardware module loaded: OK")

    def send_spacers(self):
        log.info("Starting task by sending a spacer signal on BNC1")
        sma = StateMachine(self.bpod)
        spacer = iblrig.spacer.Spacer()
        spacer.add_spacer_states(sma, next_state="exit")
        self.bpod.send_state_machine(sma)
        self.bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
        return self.bpod.session.current_trial.export()


class Frame2TTLMixin:
    """
    Frame 2 TTL interface for state machine
    """
    def init_mixin_frame2ttl(self, *args, **kwargs):
        self.frame2ttl = None

    def start_mixin_frame2ttl(self):
        # todo assert calibration
        # todo release port on failure
        self.frame2ttl = frame2TTL.frame2ttl_factory(self.hardware_settings['device_frame2ttl']['COM_F2TTL'])
        try:
            self.frame2ttl.set_thresholds(
                light=self.hardware_settings['device_frame2ttl']["F2TTL_LIGHT_THRESH"],
                dark=self.hardware_settings['device_frame2ttl']["F2TTL_DARK_THRESH"])
            log.info("Frame2TTL: Thresholds set.")
        except serial.serialutil.SerialTimeoutException as e:
            self.frame2ttl.close()
            raise e
        assert self.frame2ttl.connected
        log.info("Frame2TTL module loaded: OK")


class RotaryEncoderMixin:
    """
    Rotary encoder interface for state machine
    """
    def init_mixin_rotary_encoder(self, *args, **kwargs):
        self.device_rotary_encoder = MyRotaryEncoder(
            all_thresholds=self.task_params.STIM_POSITIONS + self.task_params.QUIESCENCE_THRESHOLDS,
            gain=self.task_params.STIM_GAIN,
            com=self.hardware_settings.device_rotary_encoder['COM_ROTARY_ENCODER'],
            connect=False
        )

    def start_mixin_rotary_encoder(self):
        try:
            self.device_rotary_encoder.connect()
        except serial.serialutil.SerialException as e:
            raise serial.serialutil.SerialException(
                "The rotary encoder COM port is already in use. This is usually due to a Bonsai process "
                "currently running on the computer. Make sure all Bonsai windows are closed prior to "
                "running the task") from e
        except Exception as e:
            raise Exception("The rotary encoder couldn't connect. If the bpod is glowing in green,"
                            "disconnect and reconnect bpod from the computer") from e
        log.info("Rotary encoder module loaded: OK")


class ValveMixin:
    def get_session_reward_amount(self: object) -> float:
        # simply returns the reward amount if no adaptive rewared is used
        if not self.task_params.ADAPTIVE_REWARD:
            return self.task_params.REWARD_AMOUNT
        # simply returns the reward amount if no adaptive rewared is used
        if not self.task_params.ADAPTIVE_REWARD:
            return self.task_params.REWARD_AMOUNT
        else:
            raise NotImplementedError
        # todo: training choice world reward from session to session
        # first session : AR_INIT_VALUE, return
        # if total_water_session < (subject_weight / 25):
        #   minimum(last_reward + AR_STEP, AR_MAX_VALUE)  3 microliters AR_MAX_VALUE
        # last ntrials strictly below 200:
        #   keep the same reward
        # trial between 200 and above:
        #   maximum(last_reward - AR_STEP, AR_MIN_VALUE)  1.5 microliters AR_MIN_VALUE

        # when implementing this make sure the test is solid

    def init_mixin_valve(self: object):
        self.valve = Bunch({})
        # the template settings files have a date in 2099, so assume that the rig is not calibrated if that is the case
        # the assertion on calibration is thrown when starting the device
        self.valve['is_calibrated'] = datetime.date.today() > self.hardware_settings['device_valve']['WATER_CALIBRATION_DATE']
        self.valve['fcn_vol2time'] = scipy.interpolate.pchip(
            self.hardware_settings['device_valve']["WATER_CALIBRATION_WEIGHT_PERDROP"],
            self.hardware_settings['device_valve']["WATER_CALIBRATION_OPEN_TIMES"],
        )

    def start_mixin_valve(self):
        # if the rig is not on manual settings, then the reward valve has to be calibrated to run the experiment
        assert self.task_params.AUTOMATIC_CALIBRATION is False or self.valve['is_calibrated'], """
            ##########################################
            NO CALIBRATION INFORMATION FOUND IN HARDWARE SETTINGS:
            Calibrate the rig or use a manual calibration
            PLEASE GO TO the task settings yaml file and set:
                'AUTOMATIC_CALIBRATION': false
                'CALIBRATION_VALUE' = <MANUAL_CALIBRATION>
            ##########################################"""
        # regardless of the calibration method, the reward valve time has to be lower than 1 second
        assert self.compute_reward_time(amount_ul=1.5) < 1,\
            """
            ##########################################
                REWARD VALVE TIME IS TOO HIGH!
            Probably because of a BAD calibration file
            Calibrate the rig or use a manual calibration
            PLEASE GO TO the task settings yaml file and set:
                AUTOMATIC_CALIBRATION = False
                CALIBRATION_VALUE = <MANUAL_CALIBRATION>
            ##########################################"""
        log.info("Water valve module loaded: OK")

    def compute_reward_time(self, amount_ul=None):
        amount_ul = amount_ul or self.task_params.REWARD_AMOUNT_UL
        if self.task_params.AUTOMATIC_CALIBRATION:
            return self.valve['fcn_vol2time'](amount_ul) / 1e3
        else:  # this is the manual manual calibration value
            return self.task_params.CALIBRATION_VALUE / 3 * amount_ul

    def valve_open(self, reward_valve_time):
        sma = StateMachine(self.bpod)
        sma.add_state(
            state_name="valve_open",
            state_timer=reward_valve_time,
            output_actions=[("Valve1", 255), ("BNC1", 255)],  # To FPGA
            state_change_conditions={"Tup": "exit"},
        )
        self.bpod.send_state_machine(sma)
        self.run_state_machine(sma)  # Locks until state machine 'exit' is reached
        return self.bpod.session.current_trial.export()


class SoundMixin:
    """
    Sound interface methods for state machine
    """
    def init_mixin_sound(self):
        self.sound = Bunch({
            'GO_TONE': None,
            'WHITE_NOISE': None,
            'OUT_TONE': None,
            'OUT_NOISE': None,
            'OUT_STOP_SOUND': None,
        })

    def start_mixin_sound(self):
        """
        Depends on bpod mixin start for hard sound card
        :return:
        """
        sound_output = self.hardware_settings.device_sound['OUTPUT']
        # sound device sd is actually the module soundevice imported above.
        # not sure how this plays out when referenced outside of this python file
        self.sound['sd'], self.sound['samplerate'], self.sound['channels'] = sound_device_factory(output=sound_output)
        # Create sounds and output actions of state machine
        self.sound['GO_TONE'] = iblrig.sound.make_sound(
            rate=self.sound['samplerate'],
            frequency=self.task_params.GO_TONE_FREQUENCY,
            duration=self.task_params.GO_TONE_DURATION,
            amplitude=self.task_params.GO_TONE_AMPLITUDE,
            fade=0.01,
            chans=self.sound['channels'])

        self.sound['WHITE_NOISE'] = iblrig.sound.make_sound(
            rate=self.sound['samplerate'],
            frequency=-1,
            duration=self.task_params.WHITE_NOISE_DURATION,
            amplitude=self.task_params.WHITE_NOISE_AMPLITUDE,
            fade=0.01,
            chans=self.sound['channels'])

        # SoundCard config params
        if self.hardware_settings.device_sound['OUTPUT'] == 'harp':
            sound.configure_sound_card(
                sounds=[self.sound.GO_TONE, self.sound.WHITE_NOISE],
                indexes=[self.task_params.GO_TONE_IDX, self.task_params.WHITE_NOISE_IDX],
                sample_rate=self.sound['samplerate'],
            )
            self.bpod.define_harp_sounds_actions(
                self.task_params.GO_TONE_IDX,
                self.task_params.WHITE_NOISE_IDX)
            self.sound['OUT_TONE'] = self.bpod.actions['play_tone']
            self.sound['OUT_NOISE'] = self.bpod.actions['play_noise']
            self.sound['OUT_STOP_SOUND'] = self.bpod.actions['stop_sound']
        else:  # xonar or system default
            self.sound['OUT_TONE'] = ("SoftCode", 1)
            self.sound['OUT_NOISE'] = ("SoftCode", 2)
            self.sound['OUT_STOP_SOUND'] = ("SoftCode", 0)
        log.info(f"Sound module loaded: OK: {sound_output}")

    def play_tone(self):
        self.sound.sd.play(self.sound.GO_TONE, self.sound['samplerate'])

    def play_noise(self):
        self.sound.sd.play(self.sound.WHITE_NOISE, self.sound['samplerate'])

    def stop_sound(self):
        self.sound.sd.stop()
