#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: iblrig/postfc.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Thursday, August 26th 2021, 5:02:19 pm
import iblrig.bonsai as bonsai
import iblrig.path_helper as ph
from iblrig.bpod_helper import bpod_lights
from iblrig.poop_count import poop
from pathlib import Path
import os


def bonsai_close_all() -> None:
    """Close all possible bonsai workflows that have a /x switch
    Closing a workflow that is not running returns no error"""
    # Close stimulus, camera, and mic workflows
    stim_client = bonsai.osc_client("stim")
    camera_client = bonsai.osc_client("camera")
    mic_client = bonsai.osc_client("mic")
    if stim_client is not None:
        stim_client.send_message("/x", 1)
        print("Closed: stim workflow")
    if camera_client is not None:
        camera_client.send_message("/x", 1)
        print("Closed: camera workflow")
    if mic_client is not None:
        mic_client.send_message("/x", 1)
        print("Closed: mic workflow")
    return


def cleanup_pybpod_data() -> None:
    experiments_folder = Path(ph.get_iblrig_params_folder()) / "IBL" / "experiments"
    sess_folders = experiments_folder.rglob("sessions")
    for s in sess_folders:
        if "setups" in str(s):
            os.system(f"rd /s /q {str(s)}")


def habituation_close():
    # Close stimulus, camera, and mic workflows
    bonsai_close_all()
    # Turn bpod lights back on
    bpod_lights(None, 1)
    # Log poop count (for latest session on rig)
    poop()
    # Cleanup pybpod data
    cleanup_pybpod_data()
    # Finally if Alyx is present try to register session and update the params in lab_location
