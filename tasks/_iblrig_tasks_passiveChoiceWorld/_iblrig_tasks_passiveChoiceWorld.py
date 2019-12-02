#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, November 15th 2019, 12:05:29 pm
import logging
import time

import numpy as np
import usb
from pybpodapi.protocol import Bpod, StateMachine

import iblrig.bonsai as bonsai
import iblrig.frame2TTL as frame2TTL
import iblrig.iotasks as iotasks
import iblrig.misc as misc
import iblrig.params as params
import task_settings
import user_settings 
from iblrig.rotary_encoder import MyRotaryEncoder
from session_params import SessionParamHandler

log = logging.getLogger('iblrig')
log.setLevel(logging.INFO)

PARAMS = params.load_params_file()
# start sph
sph = SessionParamHandler(task_settings, user_settings)
# frame2TTL seg thresholds
if frame2TTL.get_and_set_thresholds() == 0:
    sph.F2TTL_GET_AND_SET_THRESHOLDS = True
# Rotary encoder
re = MyRotaryEncoder(sph.ALL_THRESHOLDS, sph.STIM_GAIN, sph.PARAMS['COM_ROTARY_ENCODER'])
sph.ROTARY_ENCODER = re


# get bpod
bpod = Bpod(serial_port=PARAMS['COM_BPOD'])
# get soundcard bpod style
bpod_sound_card = [x for x in bpod.modules if x.name == 'SoundCard1'][0]
# Play tone
sc_play_tone = 2
bpod.load_serial_message(bpod_sound_card, sc_play_tone, [ord('P'), sph.GO_TONE_IDX])
# Play noise
sc_play_noise = 3
bpod.load_serial_message(bpod_sound_card, sc_play_noise, [ord('P'), sph.WHITE_NOISE_IDX])

# get soundcard
card = usb.core.find(idVendor=0x04d8, idProduct=0xee6a)
card_play_tone = bytes(np.array([2, 6, 32, 255, 2, 2, 0, 43], dtype=np.int8))
card_play_noise = bytes(np.array([2, 6, 32, 255, 2, 3, 0, 44], dtype=np.int8))


def do_gabor(osc_client, pcs_idx, pos, cont, phase):
    # send pcs to Bonsai
    bonsai.send_stim_info(sph.OSC_CLIENT, pcs_idx, int(pos), cont, phase,
                          freq=0.10, angle=0., gain=4., sigma=7.)

    sph.OSC_CLIENT.send_message("/re", 2)  # show_stim 2
    time.sleep(0.3)
    sph.OSC_CLIENT.send_message("/re", 1)  # stop_stim 1


def do_valve_click(bpod, reward_valve_time):
    sma = StateMachine(bpod)
    sma.add_state(
        state_name='valve_open',
        state_timer=reward_valve_time,
        output_actions=[('Valve1', 255),
                        ('BNC1', 255)],  # To FPGA
        state_change_conditions={'Tup': 'exit'},
    )
    bpod.send_state_machine(sma)
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
    return


def do_bpod_sound(bpod, sound_msg):
    sma = StateMachine(bpod)
    sma.add_state(
        state_name='play_tone',
        state_timer=0,
        output_actions=[('Serial3', sound_msg)],
        state_change_conditions={'BNC2Low': 'exit'},
    )
    bpod.send_state_machine(sma)
    bpod.run_state_machine(sma)  # Locks until state machine 'exit' is reached
    return


def do_card_sound(card, sound_msg):
    if card is not None:
        card.write(1, sound_msg, 100)
    return


# Run the passive part i.e. spontaneous activity and RFMapping stim
bonsai.start_passive_visual_stim(sph.SESSION_RAW_DATA_FOLDER)  # Loks

# start Bonsai stim workflow
bonsai.start_visual_stim(sph)
time.sleep(3)
log.info('Starting replay of task stims')
pcs_idx = 0
scount = 1
for sdel, sid in zip(sph.STIM_DELAYS, sph.STIM_IDS):
    log.info(f"Delay: {sdel}; ID: {sid}; Count: {scount}/300")
    time.sleep(sdel)
    if sid == 'V':
        # Make bpod task with 1 state = valve_open -> exit
        do_valve_click(bpod, sph.REWARD_VALVE_TIME)
        # time.sleep(sph.REWARD_VALVE_TIME)
    elif sid == 'T':
        do_bpod_sound(bpod, sc_play_tone)
        # do_card_sound(card, card_play_tone)
        # time.sleep(0.1)
    elif sid == 'N':
        do_bpod_sound(bpod, sc_play_noise)
        # do_card_sound(card, card_play_noise)
        # time.sleep(0.5)
    elif sid == 'G':
        do_gabor(sph.OSC_CLIENT,
                 pcs_idx,
                 sph.POSITIONS[pcs_idx],
                 sph.CONTRASTS[pcs_idx],
                 sph.STIM_PHASE[pcs_idx])
        pcs_idx += 1
        # time.sleep(0.3)
    scount += 1

# Patch the PYBPOD_PROTOCOL to _iblrig_tasks_ephysMockChoiceWorld if mock
if sph.IS_MOCK:
    patch = {
        'PYBPOD_PROTOCOL': '_iblrig_tasks_ephysMockChoiceWorld'
    }
    misc.patch_settings_file(sph.SETTINGS_FILE_PATH, patch=patch)
# Create a transfer_me.flag file
misc.create_flag(sph.SESSION_FOLDER, 'move_me')


if __name__ == "__main__":
    preloaded_session_num = 'mock'
    # Load session PCS
    position, contrast, phase = iotasks.load_passive_session_pcs(preloaded_session_num)
    # Load session stimDelays, stimIDs
    stimDelays, stimIDs = iotasks.load_passive_session_delays_ids(preloaded_session_num)
    print('.')
