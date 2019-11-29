#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, February 5th 2019, 5:56:17 pm
import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger('iblrig')


# =====================================================================
# SESSION PARAM HANDLER OBJECT METHODS
# =====================================================================
def start_visual_stim(sph):
    if sph.USE_VISUAL_STIMULUS and sph.BONSAI:
        # Run Bonsai workflow
        here = os.getcwd()
        os.chdir(str(
            Path(sph.VISUAL_STIM_FOLDER) / sph.VISUAL_STIMULUS_TYPE))
        bns = sph.BONSAI
        wkfl = sph.VISUAL_STIMULUS_FILE

        evt = "-p:Stim.FileNameEvents=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderEvents.raw.ssv")
        pos = "-p:Stim.FileNamePositions=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderPositions.raw.ssv")
        itr = "-p:Stim.FileNameTrialInfo=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderTrialInfo.raw.ssv")
        screen_pos = "-p:Stim.FileNameStimPositionScreen=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_stimPositionScreen.raw.ssv")

        com = "-p:Stim.REPortName=" + sph.PARAMS['COM_ROTARY_ENCODER']

        sync_x = "-p:Stim.sync_x=" + str(sph.SYNC_SQUARE_X)
        sync_y = "-p:Stim.sync_y=" + str(sph.SYNC_SQUARE_Y)
        dist = 7 if 'ephys' in sph.PYBPOD_BOARD else 8
        translationz = "-p:Stim.TranslationZ=-" + str(dist)
        start = '--start'
        noeditor = '--no-editor'
        noboot = '--no-boot'

        if sph.BONSAI_EDITOR:
            editor = start
        elif not sph.BONSAI_EDITOR:
            editor = noeditor

        if 'habituation' in sph.PYBPOD_PROTOCOL or 'bpod_ttl_test' in sph.PYBPOD_PROTOCOL:
            subprocess.Popen(
                [bns, wkfl, editor, noboot, evt, itr, com, sync_x, sync_y])
        elif 'passive' in sph.PYBPOD_PROTOCOL:
            subprocess.Popoen(
                [bns, wkfl, editor, noboot, translationz]
            )
        else:
            subprocess.Popen(
                [bns, wkfl, editor, noboot, screen_pos, pos, evt, itr, com, sync_x, sync_y,
                 translationz])
        os.chdir(here)
    else:
        sph.USE_VISUAL_STIMULUS = False
    time.sleep(2)
    return


def start_camera_recording(sph):
    if (sph.RECORD_VIDEO is False and sph.OPEN_CAMERA_VIEW is False):
        log.error("Task will hang waiting for camera frame sync pulse")
        raise(UnboundLocalError)
        return
    # Run Workflow
    here = os.getcwd()
    os.chdir(sph.VIDEO_RECORDING_FOLDER)

    bns = sph.BONSAI
    wkfl = sph.VIDEO_RECORDING_FILE

    ts = '-p:TimestampsFileName=' + os.path.join(
        sph.SESSION_RAW_VIDEO_DATA_FOLDER,
        '_iblrig_leftCamera.timestamps.ssv')
    vid = '-p:VideoFileName=' + os.path.join(
        sph.SESSION_RAW_VIDEO_DATA_FOLDER,
        '_iblrig_leftCamera.raw.avi')
    rec = '-p:SaveVideo=' + str(sph.RECORD_VIDEO)

    mic = "-p:FileNameMic=" + os.path.join(
        sph.SESSION_RAW_DATA_FOLDER, "_iblrig_micData.raw.wav")
    srec = "-p:RecordSound=" + str(sph.RECORD_SOUND)

    start = '--start'
    noboot = '--no-boot'

    subprocess.Popen([bns, wkfl, start, ts, vid, rec, mic, srec, noboot])
    os.chdir(here)
    return


# =====================================================================
# TRIAL PARAM HANDLER OBJECT METHODS
# =====================================================================
def send_current_trial_info(tph):
    """
    Sends all info relevant for stim production to Bonsai using OSC
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
    """
    if tph.osc_client is None:
        log.error("Can't send trial info to Bonsai osc_client = None")
        raise UnboundLocalError("Can't send trial info to Bonsai osc_client = None")
    # tph.position = tph.position  # (2/3)*t_position/180
    tph.osc_client.send_message("/t", tph.trial_num)
    tph.osc_client.send_message("/p", tph.position)
    tph.osc_client.send_message("/h", tph.stim_phase)
    if 'training' in tph.task_protocol:
        tph.osc_client.send_message("/c", tph.contrast.value)
    else:
        tph.osc_client.send_message("/c", tph.contrast)
    tph.osc_client.send_message("/f", tph.stim_freq)
    tph.osc_client.send_message("/a", tph.stim_angle)
    tph.osc_client.send_message("/g", tph.stim_gain)
    tph.osc_client.send_message("/s", tph.stim_sigma)


def send_stim_info(osc_client, trial_num, position, contrast, phase,
                   freq=0.10, angle=0., gain=4., sigma=7.):
    if osc_client is None:
        log.error("Can't send trial info to Bonsai osc_client = None")
        raise UnboundLocalError("Can't send trial info to Bonsai osc_client = None")
    osc_client.send_message("/t", trial_num)
    osc_client.send_message("/p", position)
    osc_client.send_message("/h", phase)
    osc_client.send_message("/c", contrast)
    # Consatants
    osc_client.send_message("/f", freq)
    osc_client.send_message("/a", angle)
    osc_client.send_message("/g", gain)
    osc_client.send_message("/s", sigma)
