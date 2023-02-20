"""
This modules contains hardware classes used to interact with modules.
"""
from pathlib import Path
import json
import os
import logging

import numpy as np
from iblutil.util import Bunch

import sounddevice as sd
from pybpod_rotaryencoder_module.module import RotaryEncoder
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
from pybpodapi.bpod.bpod_io import BpodIO

log = logging.getLogger(__name__)


class Bpod(BpodIO):

    def __init__(self, *args, **kwargs):
        super(Bpod, self).__init__(*args, **kwargs)
        self.default_message_idx = 0
        self.actions = Bunch({})

    @property
    def is_connected(self):
        return self.modules is not None

    @property
    def rotary_encoder(self):
        return self.get_module("rotary_encoder")

    @property
    def sound_card(self):
        return self.get_module("sound_card")

    def get_module(self, module: str):
        if self.modules is None:
            return None
        if module in ["re", "rotary_encoder", "RotaryEncoder"]:
            mod_name = "RotaryEncoder1"
        elif module in ["sc", "sound_card", "SoundCard"]:
            mod_name = "SoundCard1"
        mod = [x for x in self.modules if x.name == mod_name]
        if mod:
            return mod[0]

    def _define_message(self, module, message):
        """
        This loads a message in the bpod interface and can then be defined as an output
        state in the state machine
        example
        >>> id_msg_bonsai_show_stim = self._define_message(self.rotary_encoder,[ord("#"), 2])
        will then be used as such in StateMachine:
        >>> output_actions=[("Serial1", id_msg_bonsai_show_stim)]
        :param message:
        :return:
        """
        if module is None:
            return
        self.load_serial_message(module, self.default_message_idx + 1, message)
        self.default_message_idx += 1
        return self.default_message_idx

    def define_harp_sounds_actions(self, go_tone_index, noise_index, sound_port='Serial3'):
        self.actions.update({
            'play_tone': (sound_port, self._define_message(self.sound_card, [ord("P"), go_tone_index])),
            'play_noise': (sound_port, self._define_message(self.sound_card, [ord("P"), noise_index])),
            'stop_sound': (sound_port, ord("X")),
        })

    def define_rotary_encoder_actions(self, re_port='Serial1'):
        """
        Each output action is a tuple with the port and the message id
        :param go_tone_index:
        :param noise_index:
        :return:
        """
        self.actions.update({
            'rotary_encoder_reset': (re_port, self._define_message(
                self.rotary_encoder, [RotaryEncoder.COM_SETZEROPOS, RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS])),
            'bonsai_hide_stim': (re_port, self._define_message(self.rotary_encoder, [ord("#"), 1])),
            'bonsai_show_stim': (re_port, self._define_message(self.rotary_encoder, [ord("#"), 2])),
            'bonsai_closed_loop': (re_port, self._define_message(self.rotary_encoder, [ord("#"), 3])),
            'bonsai_freeze_stim': (re_port, self._define_message(self.rotary_encoder, [ord("#"), 4])),
            'bonsai_show_center': (re_port, self._define_message(self.rotary_encoder, [ord("#"), 5])),
        })

    def get_ambient_sensor_reading(self, save_to=None):
        ambient_module = [x for x in self.modules if x.name == "AmbientModule1"][0]
        ambient_module.start_module_relay()
        self.bpod_modules.module_write(ambient_module, "R")
        reply = self.bpod_modules.module_read(ambient_module, 12)
        ambient_module.stop_module_relay()

        Measures = {
            "Temperature_C": np.frombuffer(bytes(reply[:4]), np.float32),
            "AirPressure_mb": np.frombuffer(bytes(reply[4:8]), np.float32) / 100,
            "RelativeHumidity": np.frombuffer(bytes(reply[8:]), np.float32),
        }

        if save_to is not None:
            data = {k: v.tolist() for k, v in Measures.items()}
            with open(Path(save_to).joinpath("_iblrig_ambientSensorData.raw.jsonable"), "a") as f:
                f.write(json.dumps(data))
                f.write("\n")
                f.flush()

        return {k: v.tolist()[0] for k, v in Measures.items()}

    def bpod_lights(self, command: int):
        fpath = Path(self.IBLRIG_FOLDER) / "scripts" / "bpod_lights.py"
        os.system(f"python {fpath} {command}")


class MyRotaryEncoder(object):
    def __init__(self, all_thresholds, gain, com, connect=False):
        self.RE_PORT = com
        self.WHEEL_PERIM = 31 * 2 * np.pi  # = 194,778744523
        self.deg_mm = 360 / self.WHEEL_PERIM
        self.mm_deg = self.WHEEL_PERIM / 360
        self.factor = 1 / (self.mm_deg * gain)
        self.SET_THRESHOLDS = [x * self.factor for x in all_thresholds]
        self.ENABLE_THRESHOLDS = [(True if x != 0 else False) for x in self.SET_THRESHOLDS]
        # ENABLE_THRESHOLDS needs 8 bools even if only 2 thresholds are set
        while len(self.ENABLE_THRESHOLDS) < 8:
            self.ENABLE_THRESHOLDS.append(False)

        # Names of the RE events generated by Bpod
        self.ENCODER_EVENTS = [
            "RotaryEncoder1_{}".format(x) for x in list(range(1, len(all_thresholds) + 1))
        ]
        # Dict mapping threshold crossings with name ov RE event
        self.THRESHOLD_EVENTS = dict(zip(all_thresholds, self.ENCODER_EVENTS))
        if connect:
            self.connect()

    def reprJSON(self):
        d = self.__dict__
        return d

    def connect(self):
        if self.RE_PORT == "COM#":
            return
        m = RotaryEncoderModule(self.RE_PORT)
        m.set_zero_position()  # Not necessarily needed
        m.set_thresholds(self.SET_THRESHOLDS)
        m.enable_thresholds(self.ENABLE_THRESHOLDS)
        m.enable_evt_transmission()
        m.close()


def sound_device_factory(output="sysdefault", samplerate=None):
    """
    Will import, configure, and return sounddevice module to play sounds using onboard sound card.
    Parameters
    ----------
    output
        defaults to "sysdefault", should be 'xonar' or 'harp'
    samplerate
        audio sample rate, defaults to 44100
    """
    if output == "xonar":
        samplerate = samplerate or 192000
        devices = sd.query_devices()
        sd.default.device = next((i for i, d in enumerate(devices) if "XONAR SOUND CARD(64)" in d["name"]), None)
        sd.default.latency = "low"
        sd.default.channels = 2
        channels = 'L+TTL'
        sd.default.samplerate = samplerate
    elif output == "harp":
        samplerate = samplerate or 96000
        sd.default.samplerate = samplerate
        sd.default.channels = 2
        channels = 'stereo'
    elif output == "sysdefault":
        samplerate = samplerate or 44100
        sd.default.latency = "low"
        sd.default.channels = 2
        sd.default.samplerate = samplerate
        channels = 'stereo'
    return sd, samplerate, channels
