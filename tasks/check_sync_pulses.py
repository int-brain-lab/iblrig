# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, February 25th 2019, 2:10:38 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 25-02-2019 02:10:41.4141
import logging
from misc import get_port_events

log = logging.getLogger('iblrig')


def sync_check(tph):
    events = tph.trial_data['behavior_data']['Events timestamps']
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
