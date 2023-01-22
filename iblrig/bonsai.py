import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from iblrig import path_helper

log = logging.getLogger("iblrig")


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
