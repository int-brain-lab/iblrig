#!/usr/bin/env python
"""Prepare video PC for video recording session.

TODO Replace print statements with iblrig logging.
TODO Drop videopc params in favour of iblrig hardware params
TODO Get number of videos from hardware settings with command line override
 for running a subset of the configured cams
"""
import argparse
import datetime
import subprocess
from pathlib import Path

from ibllib.pipes.misc import load_videopc_params
from one.alf.io import next_num_folder

from iblrig.transfer_experiments import VideoCopier
from iblrig.path_helper import load_settings_yaml, get_local_and_remote_paths

import config_cameras as cams
from video_lengths import main as len_files


def get_activated_environment(ignore=False):
    envs = (
        subprocess.run(
            "conda env list",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
        .split()
    )
    current_env = envs[envs.index("*") - 1]

    return current_env


def launch_three_videos_acquisition(mouse: str, training_session: bool = False, new: bool = False) -> None:
    """

    Parameters
    ----------
    mouse : str
        The subject name.
    training_session : bool
        If true, assumes single camera setup.
    new : bool
        Currently unused. I assume this would determine whether to iterate the session number.
    """
    SUBJECT_NAME = mouse
    PARAMS = load_videopc_params()
    DATA_FOLDER = Path(PARAMS["DATA_FOLDER_PATH"])
    VIDEOPC_FOLDER_PATH = Path(__file__).absolute().parent

    # For now assert iblrig settings match old settings
    assert DATA_FOLDER == (tmp := get_local_and_remote_paths().local_subjects_folder), f'{DATA_FOLDER} does not equal {tmp}'

    BONSAI = VIDEOPC_FOLDER_PATH / "bonsai" / "bin" / "Bonsai.exe"
    BONSAI_WORKFLOWS_PATH = BONSAI.parent.parent / "workflows"
    SETUP_FILE = BONSAI_WORKFLOWS_PATH / "EphysRig_SetupCameras.bonsai"
    RECORD_FILE = BONSAI_WORKFLOWS_PATH / "EphysRig_SaveVideo_EphysTasks.bonsai"
    if training_session:
        RECORD_FILE = BONSAI_WORKFLOWS_PATH / "EphysRig_SaveVideo_TrainingTasks.bonsai"

    DATE = datetime.datetime.now().date().isoformat()
    NUM = next_num_folder(DATA_FOLDER / SUBJECT_NAME / DATE)

    session_path = DATA_FOLDER / SUBJECT_NAME / DATE / NUM
    collection_folder = session_path / 'raw_video_data'
    collection_folder.mkdir(parents=True, exist_ok=True)
    print(f'Created {collection_folder}')

    # Save the stub files locally and in the remote repo for future copy script to use
    acq_desc = {
        'devices': {
            'cameras': {
                'right': {'collection': collection_folder.parts[-1], 'sync_label': 'audio'},
                'body': {'collection': collection_folder.parts[-1], 'sync_label': 'audio'},
                'left': {'collection': collection_folder.parts[-1], 'sync_label': 'audio'},
            },
        },
        'version': '1.0.0'
    }
    remote = Path(rig_settings['iblrig_remote_data_path'])
    copier = VideoCopier(session_path=session_path, remote_subjects_folder=remote)
    copier.initialize_experiment(acquisition_description=acq_desc)

    # Create filenames to call Bonsai
    filenamevideo = "_iblrig_{}Camera.raw.avi"
    filenameframedata = "_iblrig_{}Camera.frameData.bin"
    # Define parameters to call bonsai
    bodyidx = "-p:BodyCameraIndex=" + str(PARAMS["BODY_CAM_IDX"])
    leftidx = "-p:LeftCameraIndex=" + str(PARAMS["LEFT_CAM_IDX"])
    rightidx = "-p:RightCameraIndex=" + str(PARAMS["RIGHT_CAM_IDX"])

    body = "-p:FileNameBody=" + str(collection_folder / filenamevideo.format("body"))
    left = "-p:FileNameLeft=" + str(collection_folder / filenamevideo.format("left"))
    right = "-p:FileNameRight=" + str(collection_folder / filenamevideo.format("right"))

    bodydata = "-p:FileNameBodyData=" + str(collection_folder / filenameframedata.format("body"))
    leftdata = "-p:FileNameLeftData=" + str(collection_folder / filenameframedata.format("left"))
    rightdata = "-p:FileNameRightData=" + str(collection_folder / filenameframedata.format("right"))

    start = "--start"  # --start-no-debug
    noboot = "--no-boot"
    # noeditor = "--no-editor"
    # Force trigger mode on all cams
    cams.disable_trigger_mode()
    # Open the streaming file and start
    subprocess.call([str(BONSAI), str(SETUP_FILE), start, noboot, bodyidx, leftidx, rightidx], cwd=str(BONSAI_WORKFLOWS_PATH))
    # Force trigger mode on all cams
    cams.enable_trigger_mode()
    # Open the record_file start and wait for manual trigger mode disabling
    rec = subprocess.Popen(
        [
            str(BONSAI),
            str(RECORD_FILE),
            noboot,
            start,
            body,
            left,
            right,
            bodyidx,
            leftidx,
            rightidx,
            bodydata,
            leftdata,
            rightdata,
        ],
        cwd=str(BONSAI_WORKFLOWS_PATH)
    )
    print("\nPRESS ENTER TO START CAMERAS" * 10)
    untrigger = input("") or 1
    print("ENTER key press detected, starting cameras...")
    if untrigger:
        cams.disable_trigger_mode()
        print("\nTo terminate video acquisition, please stop and close Bonsai workflow.")
    rec.wait()
    # Check lengths
    len_files(collection_folder.parent, display=True)  # Will print out the results
    # XXX: Consider not creating the transfer flag if lengths are not good:
    #       will impact the transfer script as it requires both transfers to be completed before
    #       creating the raw_session.flag
    # Create a transfer_me.flag file
    open(collection_folder.parent / "transfer_me.flag", "w")
    print(f"\nCreated transfer flag for session {collection_folder.parent}")
    print("Video acquisition session finished.")
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare video PC for video recording session")
    parser.add_argument("mouse", help="Mouse name")
    parser.add_argument(
        "-t",
        "--training",
        default=False,
        required=False,
        action="store_true",
        help="Launch video workflow for biasedCW session on ephys rig.",
    )
    parser.add_argument(
        "--ignore-checks",
        default=False,
        required=False,
        action="store_true",
        help="Ignore ibllib and iblscripts checks",
    )
    args = parser.parse_args()
    # print(args)
    # print(type(args.mouse), type(args.training))
    launch_three_videos_acquisition(args.mouse, training_session=args.training)
