#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, January 12th 2021, 5:48:08 pm
"""
Given a specific video session_path will count and printout the number of frames for the video
the GPIO pin states and the frame counter files
"""

import sys
from pathlib import Path
import numpy as np
import cv2
import pandas as pd


def load_CameraFrameData_file(session_path, camera: str) -> pd.DataFrame:
    out_dataframe = None
    session_path = Path(session_path)
    if session_path is None:
        return
    raw_path = Path(session_path).joinpath("raw_video_data")
    # Check if csv frame data file exists
    frame_data_file = raw_path.joinpath(f"_iblrig_{camera}Camera.FrameData.csv")
    if frame_data_file.exists():
        fdata = pd.read_csv(frame_data_file)
        out_dataframe = fdata
    # Check if bin frame data file exists
    frame_data_file = raw_path.joinpath(f"_iblrig_{camera}Camera.frameData.bin")
    if frame_data_file.exists():
        fdata = np.fromfile(frame_data_file, dtype=np.float64)
        assert len(fdata) % 4 == 0, "Missing values: expected length of array is not % 4"
        rows = int(len(fdata) / 4)
        fdata_values = np.reshape(fdata.astype(np.int64), (rows, 4))
        columns = [
            "Timestamp",  # UTC ticks
            "Value.Metadata.embeddedTimeStamp",
            "Value.Metadata.embeddedFrameCounter",
            "Value.Metadata.embeddedGPIOPinState"
        ]
        out_dataframe = pd.DataFrame(fdata_values, columns=columns)
    return out_dataframe


def load_embedded_frame_data(session_path, camera: str, raw=False):
    """
    :param session_path:
    :param camera: The specific camera to load, one of ('left', 'right', 'body')
    :param raw: If True the raw data are returned without preprocessing (thresholding, etc.)
    :return: The frame counter, the pin state
    """
    session_path = Path(session_path)
    if session_path is None:
        return None, None
    raw_path = Path(session_path).joinpath("raw_video_data")
    # Load frame count
    count_file = raw_path / f"_iblrig_{camera}Camera.frame_counter.bin"
    count = np.fromfile(count_file, dtype=np.float64).astype(int) if count_file.exists() else None
    if not (count is None or raw):
        count -= count[0]  # start from zero
    # Load pin state
    pin_file = raw_path / f"_iblrig_{camera}Camera.GPIO.bin"
    pin_state = np.fromfile(pin_file, dtype=np.float64).astype(int) if pin_file.exists() else None
    if not (pin_state is None or raw):
        pin_state = pin_state > 10
    return count, pin_state


def get_video_length(video_path):
    """
    Returns video length
    :param video_path: A path to the video
    :return:
    """
    cap = cv2.VideoCapture(str(video_path))
    assert cap.isOpened(), f"Failed to open video file {video_path}"
    length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return length


def main(session_path, display=True):
    session_path = Path(session_path)
    video_lengths = [get_video_length(p) for p in session_path.rglob("*.avi")]
    data_frames = [
        load_CameraFrameData_file(session_path, camera=c) for c in ("left", "right", "body")
    ]
    len_frames = [len(df) for df in data_frames if df is not None]
    if not len_frames:
        array_lengths = [
            (a.size, b.size)
            for a, b in [
                load_embedded_frame_data(session_path, cam, raw=True)
                for cam in ("left", "right", "body")
            ]
            if (a is not None) or (b is not None)
        ]

        array_len = []
        for cam in ("left", "right", "body"):
            a, b = load_embedded_frame_data(session_path, cam, raw=True)
            if (a is not None) or (b is not None):
                array_len.append((a.size, b.size))

        frame_counter_lengths = [x[0] for x in array_lengths]
        GPIO_state_lengths = [x[1] for x in array_lengths]
        out = {
            'session_path': session_path,
            'video_lengths': video_lengths,
            'frame_counter_lengths': frame_counter_lengths,
            'GPIO_state_lengths': GPIO_state_lengths
        }
        print(
            "\n",
            session_path, "\n",
            sorted(video_lengths), "<-- Video lengths", "\n",
            sorted(frame_counter_lengths), "<-- Frame counter lengths", "\n",
            sorted(GPIO_state_lengths), "<-- GPIO state lengths", "\n",
        )
    else:
        out = {
            'session_path': session_path,
            'video_lengths': video_lengths,
            'frame_data_lengths': len_frames
        }
        if display:
            print(
                "\n",
                session_path, "\n",
                sorted(video_lengths), "<-- Video lengths", "\n",
                sorted(len_frames), "<-- Frame Data lengths", "\n",
            )
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("I need a session_path as input...")
    main(sys.argv[1])

    # session_path = r"C:\iblrig_data\Subjects\_iblrig_test_mouse\2000-01-01\001"
    # main(session_path)
    # camera= 'left'
