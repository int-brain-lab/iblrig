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
def start_visual_stim(sph_obj):
    if sph_obj.USE_VISUAL_STIMULUS and sph_obj.BONSAI:
        # Run Bonsai workflow
        here = os.getcwd()
        os.chdir(str(
            Path(sph_obj.VISUAL_STIM_FOLDER) / sph_obj.VISUAL_STIMULUS_TYPE))
        bns = sph_obj.BONSAI
        wkfl = sph_obj.VISUAL_STIMULUS_FILE

        evt = "-p:FileNameEvents=" + os.path.join(
            sph_obj.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderEvents.raw.ssv")
        pos = "-p:FileNamePositions=" + os.path.join(
            sph_obj.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderPositions.raw.ssv")
        itr = "-p:FileNameTrialInfo=" + os.path.join(
            sph_obj.SESSION_RAW_DATA_FOLDER,
            "_iblrig_encoderTrialInfo.raw.ssv")
        mic = "-p:FileNameMic=" + os.path.join(
            sph_obj.SESSION_RAW_DATA_FOLDER,
            "_iblrig_micData.raw.wav")

        com = "-p:REPortName=" + sph_obj.COM['ROTARY_ENCODER']
        rec = "-p:RecordSound=" + str(sph_obj.RECORD_SOUND)

        sync_x = "-p:sync_x=" + str(sph_obj.SYNC_SQUARE_X)
        sync_y = "-p:sync_y=" + str(sph_obj.SYNC_SQUARE_Y)
        start = '--start'
        noeditor = '--noeditor'

        if sph_obj.BONSAI_EDITOR:
            editor = start
        elif not sph_obj.BONSAI_EDITOR:
            editor = noeditor
        if 'habituation' in sph_obj.PYBPOD_PROTOCOL:
            subprocess.Popen(
                [bns, wkfl, editor, evt, itr, com, mic, rec, sync_x, sync_y])
        elif 'training' in sph_obj.PYBPOD_PROTOCOL:
            subprocess.Popen(
                [bns, wkfl, editor, pos,
                 evt, itr, com, mic, rec, sync_x, sync_y])
        time.sleep(5)
        os.chdir(here)
    else:
        sph_obj.USE_VISUAL_STIMULUS = False


def start_camera_recording(sph_obj):
    if (sph_obj.RECORD_VIDEO is False
            and sph_obj.OPEN_CAMERA_VIEW is False):
        return
    # Run Workflow
    here = os.getcwd()
    os.chdir(sph_obj.VIDEO_RECORDING_FOLDER)

    bns = sph_obj.BONSAI
    wkfl = sph_obj.VIDEO_RECORDING_FILE

    ts = '-p:TimestampsFileName=' + os.path.join(
        sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER,
        '_iblrig_leftCamera.timestamps.ssv')
    vid = '-p:VideoFileName=' + os.path.join(
        sph_obj.SESSION_RAW_VIDEO_DATA_FOLDER,
        '_iblrig_leftCamera.raw.avi')
    rec = '-p:SaveVideo=' + str(sph_obj.RECORD_VIDEO)

    start = '--start'

    subprocess.Popen([bns, wkfl, start, ts, vid, rec])
    time.sleep(1)
    os.chdir(here)


# =====================================================================
# TRIAL PARAM HANDLER OBJECT METHODS
# =====================================================================
def send_current_trial_info(tph_obj):
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
        if tph_obj.osc_client is None:
            log.error("Can't send trial info to Bonsai osc_client = None")
            raise(UnboundLocalError)
        # tph_obj.position = tph_obj.position  # (2/3)*t_position/180
        tph_obj.osc_client.send_message("/t", tph_obj.trial_num)
        tph_obj.osc_client.send_message("/p", tph_obj.position)
        tph_obj.osc_client.send_message("/h", tph_obj.stim_phase)
        tph_obj.osc_client.send_message("/c", tph_obj.contrast.value)
        tph_obj.osc_client.send_message("/f", tph_obj.stim_freq)
        tph_obj.osc_client.send_message("/a", tph_obj.stim_angle)
        tph_obj.osc_client.send_message("/g", tph_obj.stim_gain)
        tph_obj.osc_client.send_message("/s", tph_obj.stim_sigma)
