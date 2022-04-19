#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Thursday, July 4th 2019, 1:37:34 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
import argparse
import logging
import os
import shutil
from pathlib import Path
from shutil import ignore_patterns as ig

import iblrig.raw_data_loaders as raw

log = logging.getLogger('iblrig')


def main(local_folder: str, remote_folder: str, force: bool = False) -> None:
    local_folder = Path(local_folder)
    remote_folder = Path(remote_folder)

    src_session_paths = [x.parent for x in local_folder.rglob("transfer_me.flag")]

    if not src_session_paths:
        log.info("Nothing to transfer, exiting...")
        return

    # Create all dst paths
    dst_session_paths = []
    for s in src_session_paths:
        mouse = s.parts[-3]
        date = s.parts[-2]
        sess = s.parts[-1]
        d = remote_folder / mouse / date / sess
        dst_session_paths.append(d)

    for src, dst in zip(src_session_paths, dst_session_paths):
        src_flag_file = src / "transfer_me.flag"
        if force:
            shutil.rmtree(dst, ignore_errors=True)
        log.info(f"Copying subdirectories from {src} to {dst} ...")
        try:
            shutil.copytree(src, dst, ignore=ig(str(src_flag_file.name)))
        except OSError:
            log.info('An OS error occurred when attempting ot copy the subdirectories.')
        # if folder was created, delete the src flag_file and create compress_me.flag
        if dst.exists():
            settings = raw.load_settings(dst)
            if not settings:
                log.info("A _iblrig_taskSettings.raw*.json was not found.")
            dst.joinpath("raw_session.flag").touch()
            if "ephys" in settings["PYBPOD_BOARD"]:  # Any training task on an ephys rig
                log.info(f"Removing raw_session.flag file; ephys behavior rig detected")
                dst.joinpath("raw_session.flag").unlink()
            log.info(f"Copied to {remote_folder}: Session {src_flag_file.parent}")
            try:
                src_flag_file.unlink()
            except FileNotFoundError:
                log.info('When attempting to delete the following file, it could not be found: ' +
                         str(src_flag_file))

        # Cleanup
        src_video_file = src / "raw_video_data" / "_iblrig_leftCamera.raw.avi"
        dst_video_file = dst / "raw_video_data" / "_iblrig_leftCamera.raw.avi"
        src_audio_file = src / "raw_behavior_data" / "_iblrig_micData.raw.wav"
        dst_audio_file = dst / "raw_behavior_data" / "_iblrig_micData.raw.wav"

        if (src_audio_file.exists() and
                src_audio_file.stat().st_size == dst_audio_file.stat().st_size):
            try:
                src_audio_file.unlink()
            except FileNotFoundError:
                log.info('When attempting to delete the following file, it could not be found: ' +
                         str(src_audio_file))

        if (src_video_file.exists() and
                src_video_file.stat().st_size == dst_video_file.stat().st_size):
            try:
                src_video_file.unlink()
            except FileNotFoundError:
                log.info('When attempting to delete the following file, it could not be found: ' +
                         str(src_video_file))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer files to IBL local server")
    parser.add_argument("local_folder", help="Local iblrig_data/Subjects folder")
    parser.add_argument("remote_folder", help="Remote iblrig_data/Subjects folder")
    args = parser.parse_args()
    scripts_path = Path(__file__).absolute().parent
    os.system(f"python {scripts_path / 'move_passive.py'}")
    main(args.local_folder, args.remote_folder)
