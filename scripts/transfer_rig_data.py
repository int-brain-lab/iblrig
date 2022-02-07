#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Thursday, July 4th 2019, 1:37:34 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
import argparse
import json
import logging
import os
import shutil
from pathlib import Path
from shutil import ignore_patterns as ig

import iblrig.raw_data_loaders as raw
from iblrig.misc import get_session_path
from iblrig.raw_data_loaders import load_settings

log = logging.getLogger("iblrig")
log.setLevel(logging.INFO)


def get_task_protocol(session_path):
    try:
        settings = load_settings(get_session_path(session_path))
    except json.decoder.JSONDecodeError:
        log.error(f"Can't read settings for {session_path}")
        return
    if settings:
        return settings.get("PYBPOD_PROTOCOL", None)
    else:
        return


def _get_task_types_json_config():
    with open(Path(__file__).parent.joinpath("extractor_types.json")) as fp:
        task_types = json.load(fp)
    return task_types


def get_task_extractor_type(task_name):
    """
    Returns the task type string from the full pybpod task name:
    _iblrig_tasks_biasedChoiceWorld3.7.0 returns "biased"
    _iblrig_tasks_trainingChoiceWorld3.6.0 returns "training'
    :param task_name:
    :return: one of ['biased', 'habituation', 'training', 'ephys', 'mock_ephys', 'sync_ephys']
    """
    if isinstance(task_name, Path):
        task_name = get_task_protocol(task_name)
        if task_name is None:
            return
    task_types = _get_task_types_json_config()
    task_type = next((task_types[tt] for tt in task_types if tt in task_name), None)
    if task_type is None:
        log.warning(f"No extractor type found for {task_name}")
    return task_type


def get_session_extractor_type(session_path):
    """
    From a session path, loads the settings file, finds the task and checks if extractors exist
    task names examples:
    :param session_path:
    :return: bool
    """
    settings = load_settings(session_path)
    if settings is None:
        log.error(f'ABORT: No data found in "raw_behavior_data" folder {session_path}')
        return False
    extractor_type = get_task_extractor_type(settings["PYBPOD_PROTOCOL"])
    if extractor_type:
        return extractor_type
    else:
        return False


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
        log.info(f"Copying {src}...")
        shutil.copytree(src, dst, ignore=ig(str(src_flag_file.name)))
        # finally if folder was created delete the src flag_file and create compress_me.flag
        if dst.exists():
            task_type = get_session_extractor_type(Path(src))
            if task_type not in ["ephys", "ephys_sync", "ephys_mock"]:
                dst.joinpath("raw_session.flag").touch()
                settings = raw.load_settings(dst)
                if "ephys" in settings["PYBPOD_BOARD"]:  # Any traing task on an ephys rig
                    dst.joinpath("raw_session.flag").unlink()
            log.info(f"Copied to {remote_folder}: Session {src_flag_file.parent}")
            src_flag_file.unlink()

        # Cleanup
        src_video_file = src / "raw_video_data" / "_iblrig_leftCamera.raw.avi"
        dst_video_file = dst / "raw_video_data" / "_iblrig_leftCamera.raw.avi"
        src_audio_file = src / "raw_behavior_data" / "_iblrig_micData.raw.wav"
        dst_audio_file = dst / "raw_behavior_data" / "_iblrig_micData.raw.wav"

        if (
            src_audio_file.exists()
            and src_audio_file.stat().st_size == dst_audio_file.stat().st_size
        ):
            src_audio_file.unlink()

        if (
            src_video_file.exists()
            and src_video_file.stat().st_size == dst_video_file.stat().st_size
        ):
            src_video_file.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer files to IBL local server")
    parser.add_argument("local_folder", help="Local iblrig_data/Subjects folder")
    parser.add_argument("remote_folder", help="Remote iblrig_data/Subjects folder")
    args = parser.parse_args()
    scripts_path = Path(__file__).absolute().parent
    os.system(f"python {scripts_path / 'move_passive.py'}")
    main(args.local_folder, args.remote_folder)
