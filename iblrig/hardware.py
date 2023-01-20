"""
This modules contains hardware classes used to interact with modules.
"""
from pathlib import Path
import json
import os
import logging

import numpy as np

import sounddevice as sd
from pybpod_rotaryencoder_module.module import RotaryEncoder
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
from pybpod_soundcard_module.module_api import SoundCardModule

from pybpodapi.bpod.bpod_io import BpodIO

log = logging.getLogger(__name__)


class Bpod(BpodIO):

    def __init__(self, *args, **kwargs):
        super(Bpod, self).__init__(*args, **kwargs)
        self.default_message_idx = 0

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
        mod = [x for x in self.bpod.modules if x.name == mod_name]
        if mod:
            return mod[0]

    def rotary_encoder_reset(self):
        re_reset = self.default_message_idx + 1
        self.load_serial_message(
            self.rotary_encoder,
            re_reset,
            [RotaryEncoder.COM_SETZEROPOS, RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS],  # ord('Z')
        )  # ord('E')
        self.default_message_idx += 1
        return re_reset

    def bonsai_hide_stim(self):
        # Stop the stim
        bonsai_hide_stim = self.default_message_idx + 1
        self.load_serial_message(self.rotary_encoder, bonsai_hide_stim, [ord("#"), 1])
        self.default_message_idx += 1
        return bonsai_hide_stim

    def bonsai_show_stim(self):
        # Stop the stim
        bonsai_show_stim = self.default_message_idx + 1
        self.load_serial_message(self.rotary_encoder, bonsai_show_stim, [ord("#"), 2])
        self.default_message_idx += 1
        return bonsai_show_stim

    def bonsai_close_loop(self):
        # Stop the stim
        bonsai_close_loop = self.default_message_idx + 1
        self.load_serial_message(self.rotary_encoder, bonsai_close_loop, [ord("#"), 3])
        self.default_message_idx += 1
        return bonsai_close_loop

    def bonsai_freeze_stim(self):
        # Freeze the stim
        bonsai_freeze_stim = self.default_message_idx + 1
        self.load_serial_message(self.rotary_encoder, bonsai_freeze_stim, [ord("#"), 4])
        self.default_message_idx += 1
        return bonsai_freeze_stim

    def bonsai_show_center(self):
        # Freeze the stim
        bonsai_freeze_stim = self.default_message_idx + 1
        self.load_serial_message(self.rotary_encoder, bonsai_freeze_stim, [ord("#"), 5])
        self.default_message_idx += 1
        return bonsai_freeze_stim

    def sound_card_play_idx(self, tone_idx):
        if self.sound_card is None:
            return
        sc_play_idx = self.default_message_idx + 1
        self.load_serial_message(self.sound_card, sc_play_idx, [ord("P"), tone_idx])
        self.default_message_idx += 1
        return sc_play_idx

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


class SoundDevice(object):
    def __init__(self, output="sysdefault", samplerate=None):
        """
        Will import, configure, and return sounddevice module to play sounds using onboard sound card.
        Parameters
        ----------
        output
            defaults to "sysdefault", should be 'xonar' or None
        samplerate
            audio sample rate, defaults to 44100
        """
        # FIXME: wait what ?!? is the None option for the HARP sound card ?
        if output is None:
            return
        self.output = output
        self.card = SoundCardModule()
        self.samplerate = samplerate
        if self.samplerate is None:
            if self.output == "sysdefault":
                self.samplerate = 44100
            elif self.output == "xonar":
                self.samplerate = 192000
            elif self.output is None:
                self.samplerate = 96000
            else:
                log.error("SOFT_SOUND in not: 'sysdefault', 'xonar' or 'None'")
                raise (NotImplementedError)

        if self.output == "xonar":
            devices = sd.query_devices()
            self.device = next(((i, d) for i, d in enumerate(devices) if "XONAR SOUND CARD(64)" in d["name"]), None)
            self.latency = "low"
            self.n_channels = 2
            self.channels = 'L+TTL'
        elif self.output == "sysdefault":
            self.latency = "low"
            self.n_channels = 2
            self.channels = 'stereo'
