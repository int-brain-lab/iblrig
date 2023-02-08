import argparse
import logging
import os
from ibllib.pipes.misc import rsync_paths
from pathlib import Path

import iblrig.raw_data_loaders as raw

log = logging.getLogger("iblrig")


def main(local_dir: str, remote_dir: str) -> None:
    """
    Function to move local session data to a remote location

    Parameters
    ----------
    local_dir - Local iblrig_data/Subjects dir
    remote_dir - Remote iblrig_data/Subjects dir

    Returns
    -------
    None
    """
    # Cast argument strings to Path
    local_dir = Path(local_dir)
    remote_dir = Path(remote_dir)

    # Determine which local dirs have the transfer_me.flag present
    src_session_paths = [x.parent for x in local_dir.rglob("transfer_me.flag")]

    # Exit script if no transfer_me.flag files are present
    if not src_session_paths:
        log.info("Nothing to transfer, exiting...")
        return

    # Build out destination path and call rsync to move
    for src in src_session_paths:
        mouse = src.parts[-3]
        date = src.parts[-2]
        sess = src.parts[-1]
        dst = remote_dir / mouse / date / sess
        log.info(f"Attempting to copy subdirectories from {src} to {dst}...")
        if not rsync_paths(src, dst):  # if calling rsync_paths did not return true
            log.error(f"Something went wrong copying files from {src} to {dst}...")
            return  # exit the script
        else:
            log.info("..subdirectories copied successfully, removing local transfer_me.flag file.")
            src.joinpath("transfer_me.flag").unlink()
            settings = raw.load_settings(src)
            if "ephys" not in settings["PYBPOD_BOARD"]:  # Any training task not on an ephys rig
                log.info("Creating raw_session.flag file")
                dst.joinpath("raw_session.flag").touch()

        # Cleanup large audio files in src directory
        src_audio_file = src / "raw_behavior_data" / "_iblrig_micData.raw.wav"
        dst_audio_file = dst / "raw_behavior_data" / "_iblrig_micData.raw.wav"
        if src_audio_file.exists() and src_audio_file.stat().st_size == dst_audio_file.stat().st_size:
            src_audio_file.unlink()

        # Cleanup large video files in src directory
        src_video_file = src / "raw_video_data" / "_iblrig_leftCamera.raw.avi"
        dst_video_file = dst / "raw_video_data" / "_iblrig_leftCamera.raw.avi"
        if src_video_file.exists() and src_video_file.stat().st_size == dst_video_file.stat().st_size:
            src_video_file.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer files to IBL local server")
    parser.add_argument("local_dir", help="Local iblrig_data/Subjects dir")
    parser.add_argument("remote_dir", help="Remote iblrig_data/Subjects dir")
    args = parser.parse_args()
    scripts_path = Path(__file__).absolute().parent
    os.system(f"python {scripts_path / 'move_passive.py'}")
    main(args.local_dir, args.remote_dir)
