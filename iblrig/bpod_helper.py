#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, December 9th 2019, 1:32:54 pm
# Rotary Encoder State Machine handler
import logging
import struct

import serial
from pybpod_rotaryencoder_module.module import RotaryEncoder

import iblrig.params as params

log = logging.getLogger("iblrig")


class BpodMessageCreator(object):
    def __init__(self, bpod):
        self.default_message_idx = 0
        self.bpod = bpod
        self.rotary_encoder = self.get_module("rotary_encoder")
        self.sound_card = self.get_module("sound_card")

    def get_module(self, module: str):
        if module in ["re", "rotary_encoder", "RotaryEncoder"]:
            mod_name = "RotaryEncoder1"
        elif module in ["sc", "sound_card", "SoundCard"]:
            mod_name = "SoundCard1"
        mod = [x for x in self.bpod.modules if x.name == mod_name]
        if mod:
            return mod[0]

    def rotary_encoder_reset(self):
        re_reset = self.default_message_idx + 1
        self.bpod.load_serial_message(
            self.rotary_encoder,
            re_reset,
            [
                RotaryEncoder.COM_SETZEROPOS,  # ord('Z')
                RotaryEncoder.COM_ENABLE_ALLTHRESHOLDS,
            ],
        )  # ord('E')
        self.default_message_idx += 1
        return re_reset

    def bonsai_hide_stim(self):
        # Stop the stim
        bonsai_hide_stim = self.default_message_idx + 1
        self.bpod.load_serial_message(self.rotary_encoder, bonsai_hide_stim, [ord("#"), 1])
        self.default_message_idx += 1
        return bonsai_hide_stim

    def bonsai_show_stim(self):
        # Stop the stim
        bonsai_show_stim = self.default_message_idx + 1
        self.bpod.load_serial_message(self.rotary_encoder, bonsai_show_stim, [ord("#"), 2])
        self.default_message_idx += 1
        return bonsai_show_stim

    def bonsai_close_loop(self):
        # Stop the stim
        bonsai_close_loop = self.default_message_idx + 1
        self.bpod.load_serial_message(self.rotary_encoder, bonsai_close_loop, [ord("#"), 3])
        self.default_message_idx += 1
        return bonsai_close_loop

    def bonsai_freeze_stim(self):
        # Freeze the stim
        bonsai_freeze_stim = self.default_message_idx + 1
        self.bpod.load_serial_message(self.rotary_encoder, bonsai_freeze_stim, [ord("#"), 4])
        self.default_message_idx += 1
        return bonsai_freeze_stim

    def bonsai_show_center(self):
        # Freeze the stim
        bonsai_freeze_stim = self.default_message_idx + 1
        self.bpod.load_serial_message(self.rotary_encoder, bonsai_freeze_stim, [ord("#"), 5])
        self.default_message_idx += 1
        return bonsai_freeze_stim

    def sound_card_play_idx(self, tone_idx):
        if self.sound_card is None:
            return
        sc_play_idx = self.default_message_idx + 1
        self.bpod.load_serial_message(self.sound_card, sc_play_idx, [ord("P"), tone_idx])
        self.default_message_idx += 1
        return sc_play_idx

    def return_bpod(self):
        return self.bpod


def bpod_lights(comport: str, command: int):
    if not comport:
        comport = params.get_board_comport()
    ser = serial.Serial(port=comport, baudrate=115200, timeout=1)
    ser.write(struct.pack("cB", b":", command))
    # ser.read(1)
    ser.close()
    log.debug(f"Sent <:{command}> to {comport}")
    return
