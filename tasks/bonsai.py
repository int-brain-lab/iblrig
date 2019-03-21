# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, February 5th 2019, 5:56:17 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 5-02-2019 05:56:19.1919
import os
import subprocess
from pathlib import Path
import time
import logging
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

        evt = "-p:FileNameEvents=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderEvents.raw.ssv")
        pos = "-p:FileNamePositions=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderPositions.raw.ssv")
        itr = "-p:FileNameTrialInfo=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderTrialInfo.raw.ssv")
        mic = "-p:FileNameMic=" + os.path.join(
            sph.SESSION_RAW_DATA_FOLDER,
            "_iblrig_micData.raw.wav")

        com = "-p:REPortName=" + sph.COM['ROTARY_ENCODER']
        rec = "-p:RecordSound=" + str(sph.RECORD_SOUND)

        sync_x = "-p:sync_x=" + str(sph.SYNC_SQUARE_X)
        sync_y = "-p:sync_y=" + str(sph.SYNC_SQUARE_Y)
        start = '--start'
        noeditor = '--noeditor'

        if sph.BONSAI_EDITOR:
            editor = start
        elif not sph.BONSAI_EDITOR:
            editor = noeditor

        if 'habituation' in sph.PYBPOD_PROTOCOL:
            subprocess.Popen(
                [bns, wkfl, editor, evt, itr, com, mic, rec, sync_x, sync_y])
        else:
            subprocess.Popen(
                [bns, wkfl, editor, pos,
                 evt, itr, com, mic, rec, sync_x, sync_y])
        time.sleep(5)
        os.chdir(here)
    else:
        sph.USE_VISUAL_STIMULUS = False


def start_camera_recording(sph):
    if (sph.RECORD_VIDEO is False
            and sph.OPEN_CAMERA_VIEW is False):
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

    start = '--start'

    subprocess.Popen([bns, wkfl, start, ts, vid, rec])
    time.sleep(1)
    os.chdir(here)


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
        raise(UnboundLocalError)
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
