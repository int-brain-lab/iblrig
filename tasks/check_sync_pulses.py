#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, February 25th 2019, 2:10:38 pm
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import ibllib.io.raw_data_loaders as raw
from misc import get_port_events

log = logging.getLogger('iblrig')


def sync_check(tph):
    events = tph.behavior_data['Events timestamps']
    ev_bnc1 = get_port_events(events, name='BNC1')
    ev_bnc2 = get_port_events(events, name='BNC2')
    ev_port1 = get_port_events(events, name='Port1')
    NOT_FOUND = 'COULD NOT FIND DATA ON {}'
    bnc1_msg = NOT_FOUND.format('BNC1') if not ev_bnc1 else 'OK'
    bnc2_msg = NOT_FOUND.format('BNC2') if not ev_bnc2 else 'OK'
    port1_msg = NOT_FOUND.format('Port1') if not ev_port1 else 'OK'
    warn_msg = f"""
        ##########################################
                NOT FOUND: SYNC PULSES
        ##########################################
        VISUAL STIMULUS SYNC: {bnc1_msg}
        SOUND SYNC: {bnc2_msg}
        CAMERA SYNC: {port1_msg}
        ##########################################"""
    if not ev_bnc1 or not ev_bnc2 or not ev_port1:
        log.warning(warn_msg)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("I need a file name...")
    session_data_file = Path(sys.argv[1])
    if not session_data_file.exists():
        raise (FileNotFoundError)
    if session_data_file.name.endswith('.jsonable'):
        data = raw.load_data(session_data_file.parent.parent)
    else:
        try:
            data = raw.load_data(session_data_file)
        except Exception:
            print('Not a file or a valid session folder')
    unsynced_trial_count = 0
    frame2ttl = []
    sound = []
    camera = []
    trial_end = []
    for trial_data in data:
        tevents = trial_data['behavior_data']['Events timestamps']
        ev_bnc1 = get_port_events(tevents, name='BNC1')
        ev_bnc2 = get_port_events(tevents, name='BNC2')
        ev_port1 = get_port_events(tevents, name='Port1')
        if not ev_bnc1 or not ev_bnc2 or not ev_port1:
            unsynced_trial_count += 1
        frame2ttl.extend(ev_bnc1)
        sound.extend(ev_bnc2)
        camera.extend(ev_port1)
        trial_end.append(trial_data['behavior_data']['Trial end timestamp'])
    print(f'Found {unsynced_trial_count} trials with bad sync data')

    f = plt.figure()  # figsize=(19.2, 10.8), dpi=100)
    ax = plt.subplot2grid((1, 1), (0, 0), rowspan=1, colspan=1)

    ax.plot(camera, np.ones(len(camera)) * 1, '|')
    ax.plot(sound, np.ones(len(sound)) * 2, '|')
    ax.plot(frame2ttl, np.ones(len(frame2ttl)) * 3, '|')
    [ax.axvline(t, alpha=0.5) for t in trial_end]
    ax.set_ylim([0, 4])
    ax.set_yticks(range(4))
    ax.set_yticklabels(['', 'camera', 'sound', 'frame2ttl'])
    plt.show()
