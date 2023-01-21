import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from sys import platform

from pythonosc import udp_client

from iblrig import path_helper

log = logging.getLogger("iblrig")

def start_mic_recording(sph):
    here = os.getcwd()
    os.chdir(sph.MIC_RECORDING_FOLDER)
    bns = sph.BONSAI
    wkfl = sph.MIC_RECORDING_FILE
    srec = "-p:RecordSound=" + str(sph.RECORD_SOUND)
    mic = "-p:FileNameMic=" + os.path.join(
        sph.SESSION_RAW_DATA_FOLDER, "_iblrig_micData.raw.wav"
    )

    start = "--start"
    noboot = "--no-boot"

    subprocess.Popen([bns, wkfl, start, mic, srec, noboot])
    os.chdir(here)
    return

def start_camera_recording(sph):
    # Run Workflow
    here = os.getcwd()
    os.chdir(sph.VIDEO_RECORDING_FOLDER)

    bns = sph.BONSAI
    wkfl = sph.VIDEO_RECORDING_FILE

    vid = "-p:FileNameLeft=" + os.path.join(
        sph.SESSION_RAW_VIDEO_DATA_FOLDER, "_iblrig_leftCamera.raw.avi"
    )
    fd = "-p:FileNameLeftData=" + os.path.join(
        sph.SESSION_RAW_VIDEO_DATA_FOLDER, "_iblrig_leftCamera.frameData.bin"
    )
    mic = "-p:FileNameMic=" + os.path.join(
        sph.SESSION_RAW_DATA_FOLDER, "_iblrig_micData.raw.wav"
    )
    srec = "-p:RecordSound=" + str(sph.RECORD_SOUND)

    start = "--start"
    noboot = "--no-boot"

    subprocess.Popen([bns, wkfl, start, vid, fd, mic, srec, noboot])
    os.chdir(here)
    return

def start_passive_visual_stim(
    save2folder,
    map_time="00:05:00",
    fname="_iblrig_RFMapStim.raw.bin",
    rate=0.1,
    sa_time="00:10:00",
    display_idx=1,
):
    here = os.getcwd()
    bns = path_helper.get_bonsai_path()
    stim_folder = str(path_helper.get_iblrig_path() / "visual_stim" / "passiveChoiceWorld")
    wkfl = os.path.join(stim_folder, "passiveChoiceWorld_passive.bonsai")
    os.chdir(stim_folder)
    # Flags
    noedit = "--no-editor"  # implies start and no-debug?
    noboot = "--no-boot"
    # Properties
    SA0_DueTime = "-p:Stim.SpontaneousActivity0.DueTime=" + sa_time
    RFM_FileName = "-p:Stim.ReceptiveFieldMappingStim.FileNameRFMapStim=" + str(
        Path(save2folder) / fname
    )
    RFM_MappingTime = "-p:Stim.ReceptiveFieldMappingStim.MappingTime=" + map_time
    RFM_StimRate = "-p:Stim.ReceptiveFieldMappingStim.Rate=" + str(rate)

    display_idx = "-p:Stim.DisplayIndex=" + str(display_idx)
    cmd = [
        bns,
        wkfl,
        noboot,
        noedit,
        display_idx,
        SA0_DueTime,
        RFM_FileName,
        RFM_MappingTime,
        RFM_StimRate,
    ]

    log.info("Starting spontaneous activity and RF mapping stims")
    os.chdir(stim_folder)
    s = subprocess.run(cmd, stdout=subprocess.PIPE)  # locking call
    os.chdir(here)
    log.info("Done")
    sys.stdout.flush()
    return s

# =====================================================================
# TRIAL PARAM HANDLER OBJECT METHODS
# =====================================================================
def send_stim_info(
    osc_client,
    trial_num,
    position,
    contrast,
    phase,
    freq=0.10,
    angle=0.0,
    gain=4.0,
    sigma=7.0,
    reverse=0,
):
    """For passive stim"""
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
    osc_client.send_message("/r", reverse)

def start_frame2ttl_test(data_file, lengths_file, harp=False, display_idx=1):
    here = os.getcwd()
    bns = path_helper.get_bonsai_path()
    stim_folder = str(path_helper.get_iblrig_path() / "visual_stim" / "f2ttl_calibration")
    wkfl = os.path.join(stim_folder, "screen_60Hz.bonsai")
    # Flags
    noedit = "--no-editor"  # implies start and no-debug?
    noboot = "--no-boot"
    display_idx = "-p:DisplayIndex=" + str(display_idx)
    data_file_name = "-p:FileNameData=" + str(data_file)
    lengths_file_name = "-p:FileNameDataLengths=" + str(lengths_file)
    if harp:
        harp_file_name = "-p:FileName=" + str(data_file.parent / "harp_ts_data.csv")
    # Properties
    log.info("Starting pulses @ 60Hz")
    sys.stdout.flush()
    os.chdir(stim_folder)
    if harp:
        s = subprocess.Popen(
            [bns, wkfl, noboot, noedit, data_file_name, lengths_file_name, harp_file_name]
        )
    else:
        s = subprocess.Popen(
            [bns, wkfl, noboot, noedit, display_idx, data_file_name, lengths_file_name]
        )
    os.chdir(here)
    return s

def start_screen_color(display_idx=1):
    here = os.getcwd()
    iblrig_folder_path = path_helper.get_iblrig_path()
    os.chdir(str(iblrig_folder_path / "visual_stim" / "f2ttl_calibration"))
    bns = path_helper.get_bonsai_path()
    wrkfl = str(iblrig_folder_path / "visual_stim" / "f2ttl_calibration" / "screen_color.bonsai")
    noedit = "--no-editor"  # implies start
    # nodebug = '--start-no-debug'
    # start = '--start'
    noboot = "--no-boot"
    editor = noedit
    display_idx = "-p:DisplayIndex=" + str(display_idx)
    subprocess.Popen([bns, wrkfl, editor, noboot, display_idx])
    time.sleep(3)
    os.chdir(here)

def start_camera_setup():
    here = os.getcwd()
    iblrig_folder_path = path_helper.get_iblrig_path()
    os.chdir(str(iblrig_folder_path / "devices" / "camera_setup"))

    bns = path_helper.get_bonsai_path()
    wrkfl = path_helper.get_camera_setup_wrkfl()

    # noedit = "--no-editor"  # implies start
    noboot = "--no-boot"
    editor = "--start-no-debug"
    subprocess.call([bns, wrkfl, editor, noboot])  # locks until Bonsai closes
    os.chdir(here)


def osc_client(workflow):
    ip = "127.0.0.1"
    if "stim" in workflow:
        port = 7110
    elif "camera" in workflow:
        port = 7111
    elif "mic" in workflow:
        port = 7112
    return udp_client.SimpleUDPClient(ip, port)


def close_all_workflows():
    """Close all possible bonsai workflows that have a /x switch
    Closing a workflow that is not running returns no error"""
    # Close stimulus, camera, and mic workflows
    stim_client = osc_client("stim")
    camera_client = osc_client("camera")
    mic_client = osc_client("mic")
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


def stop_wrkfl(name):
    ports = {
        "stim": 7110,
        "camera": 7111,
        "mic": 7112,
    }
    if name in ports:
        osc_port = ports[name]
    else:
        log.warning(f"Unknown name: {name}")
        osc_port = 0
    OSC_CLIENT_IP = "127.0.0.1"
    OSC_CLIENT_PORT = int(osc_port)
    osc_client = udp_client.SimpleUDPClient(OSC_CLIENT_IP, OSC_CLIENT_PORT)
    osc_client.send_message("/x", 1)
