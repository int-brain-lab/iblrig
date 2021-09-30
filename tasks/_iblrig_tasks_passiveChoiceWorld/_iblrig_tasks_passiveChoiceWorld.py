#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, November 15th 2019, 12:05:29 pm
import logging
import sys
import time

import numpy as np
import usb
from ibllib.graphic import popup
from pybpodapi.protocol import Bpod, StateMachine

import iblrig.bonsai as bonsai
import iblrig.frame2TTL as frame2TTL
import iblrig.iotasks as iotasks
import iblrig.misc as misc
import iblrig.params as params
import task_settings
import user_settings
from iblrig.bpod_helper import BpodMessageCreator, bpod_lights
from iblrig.rotary_encoder import MyRotaryEncoder
from session_params import SessionParamHandler

log = logging.getLogger("iblrig")
log.setLevel(logging.INFO)

PARAMS = params.load_params_file()
# start sph
sph = SessionParamHandler(task_settings, user_settings)
# frame2TTL seg thresholds
if frame2TTL.get_and_set_thresholds() == 0:
    sph.F2TTL_GET_AND_SET_THRESHOLDS = True
# Rotary encoder
re = MyRotaryEncoder(sph.ALL_THRESHOLDS, sph.STIM_GAIN, sph.PARAMS["COM_ROTARY_ENCODER"])
sph.ROTARY_ENCODER = re

# get bpod
bpod = Bpod()
# Build messages
msg = BpodMessageCreator(bpod)
sc_play_tone = msg.sound_card_play_idx(sph.GO_TONE_IDX)
sc_play_noise = msg.sound_card_play_idx(sph.WHITE_NOISE_IDX)
bpod = msg.return_bpod()

# get soundcard
card = usb.core.find(idVendor=0x04D8, idProduct=0xEE6A)
card_play_tone = bytes(np.array([2, 6, 32, 255, 2, 2, 0, 43], dtype=np.int8))
card_play_noise = bytes(np.array([2, 6, 32, 255, 2, 3, 0, 44], dtype=np.int8))


def do_gabor(osc_client, pcs_idx, pos, cont, phase):
    # send pcs to Bonsai
    bonsai.send_stim_info(
        osc_client,
        pcs_idx,
        int(pos),
        cont,
        phase,
        freq=0.10,
        angle=0.0,
        gain=4.0,
        sigma=7.0,
    )

    osc_client.send_message("/re", 2)  # show_stim 2
    time.sleep(0.3)
    osc_client.send_message("/re", 1)  # stop_stim 1


def do_valve_click(bpod, reward_valve_time):
    sma = StateMachine(bpod)
    sma.add_state(
        state_name="valve_open",
        state_timer=reward_valve_time,
        output_actions=[("Valve1", 255), ("BNC1", 255)],  # To FPGA
        state_change_conditions={"Tup": "exit"},
    )
    bpod.send_state_machine(sma)
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
    return


def do_bpod_sound(bpod, sound_msg):
    if sound_msg == sc_play_tone:
        t = 0.102
    elif sound_msg == sc_play_noise:
        t = 0.510
    sma = StateMachine(bpod)
    sma.add_state(
        state_name="play_tone",
        state_timer=t,
        output_actions=[("Serial3", sound_msg)],
        state_change_conditions={"BNC2Low": "exit", "Tup": "exit"},
    )
    bpod.send_state_machine(sma)
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
    return


def do_card_sound(card, sound_msg):
    if card is not None:
        card.write(1, sound_msg, 100)
    return


# Add warning to close the water valve
msg = (
    "You're about to start the passive stimulation protocol."
    + "\nMake sure the VALVE is turned OFF!"
)
popup("WARNING!", msg)  # Locks

# Run the passive part i.e. spontaneous activity and RFMapping stim
bonsai.start_passive_visual_stim(sph.SESSION_RAW_DATA_FOLDER)  # Locks

# start Bonsai stim workflow
bonsai.start_visual_stim(sph)
time.sleep(5)
log.info("Starting replay of task stims")
pcs_idx = 0
scount = 1
for sdel, sid in zip(sph.STIM_DELAYS, sph.STIM_IDS):
    log.info(f"Delay: {sdel}; ID: {sid}; Count: {scount}/300")
    sys.stdout.flush()
    time.sleep(sdel)
    if sid == "V":
        # Make bpod task with 1 state = valve_open -> exit
        do_valve_click(bpod, sph.REWARD_VALVE_TIME)
        # time.sleep(sph.REWARD_VALVE_TIME)
    elif sid == "T":
        do_bpod_sound(bpod, sc_play_tone)
        # do_card_sound(card, card_play_tone)
        # time.sleep(0.1)
    elif sid == "N":
        do_bpod_sound(bpod, sc_play_noise)
        # do_card_sound(card, card_play_noise)
        # time.sleep(0.5)
    elif sid == "G":
        do_gabor(
            sph.OSC_CLIENT,
            pcs_idx,
            sph.POSITIONS[pcs_idx],
            sph.CONTRASTS[pcs_idx],
            sph.STIM_PHASE[pcs_idx],
        )
        pcs_idx += 1
        # time.sleep(0.3)
    scount += 1

# FIXME: From here if task loop crashes nothing runs
# Patch the PYBPOD_PROTOCOL of both ephys and passive sessions if session is mock
if sph.IS_MOCK:
    ephys_patch = {"PYBPOD_PROTOCOL": "_iblrig_tasks_ephysMockChoiceWorld"}
    passive_patch = {"PYBPOD_PROTOCOL": "_iblrig_tasks_passiveMockChoiceWorld"}
    misc.patch_settings_file(sph.CORRESPONDING_EPHYS_SESSION, patch=ephys_patch)
    misc.patch_settings_file(sph.SETTINGS_FILE_PATH, patch=passive_patch)

# Create a flag files
misc.create_flag(sph.SESSION_FOLDER, "passive_data_for_ephys.flag")
misc.create_flag(sph.SESSION_FOLDER, "poop_count")

bpod.close()
# Turn bpod light's back on
bpod_lights(PARAMS["COM_BPOD"], 1)
# Close Bonsai stim
bonsai.stop_wrkfl("stim")
msg = "Passive protocol done, please remove subject.\n" * 42
log.info(msg)
msg = "Passive protocol is over.\nMake sure you turn the VALVE back ON!"
popup("WARNING!", msg)  # Locks

if __name__ == "__main__":
    pregenerated_session_num = "mock"
    # Load session PCS
    position, contrast, phase = iotasks.load_passive_session_pcs(pregenerated_session_num)
    # Load session stimDelays, stimIDs
    stimDelays, stimIDs = iotasks.load_passive_session_delays_ids(pregenerated_session_num)
    print(".")
