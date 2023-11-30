#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: videopc\raw_videoqc.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Thursday, October 28th 2021, 3:37:12 pm
import argparse
from pathlib import Path

from ibllib.qc.camera import CameraQC
from ibllib.io.raw_data_loaders import load_camera_ssv_times
from one.api import One


def main(session_path, display=False, seesion_type=None, label='left'):
    qc = CameraQC(session_path, label, one=One(mode='local'), stream=False)
    qc.video_path = next(session_path.joinpath('raw_video_data').glob(f'*{qc.label}Camera.raw*'))
    qc._type = seesion_type
    if not qc.type:
        n_videos = len(list(qc.video_path.parent.glob('*Camera.raw*')))
        qc._type = 'ephys' if n_videos > 1 else 'training'
    # NB: In later QC the timestamps will be the extracted camera.times.  Used in framerate check.
    qc.data['timestamps'] = load_camera_ssv_times(session_path, camera=qc.label)
    qc.load_video_data()

    # Run frame checks
    bright_outcome = qc.check_brightness(display=display)
    pos_outcome = qc.check_position(display=display)
    focus_outcome = qc.check_focus(display=display)
    print(f"Brightness: {bright_outcome}\nPosition: {pos_outcome}\nFocus: {focus_outcome}")

    # Run meta data checks
    fh_outcome = qc.check_file_headers()
    fr_outcome = qc.check_framerate()
    res_outcome = qc.check_resolution()
    print(f"File headers: {fh_outcome}\nFrame rate: {fr_outcome}\nResolution: {res_outcome}")


if __name__ == '__main__':
    # session_path = Path('C:\\iblrig_data\\Subjects\\_iblrig_test_mouse\\2021-03-30\\007')
    # main(session_path)
    parser = argparse.ArgumentParser(
        description='Run video QC on raw files')
    parser.add_argument('session_path', help='Local session path')
    parser.add_argument('-c', '--camera', default='left',
                        help='Camera label, i.e. left, right or body')
    parser.add_argument('-t', '--type', default=None, required=False,
                        help='Session type, e.g. ephys or training')
    parser.add_argument(
        '-d', '--display',
        action="store_true",
        default=False,
        required=False,
        help='Whether to display plots'
    )
    args = parser.parse_args()
    main(Path(args.session_path), display=args.display, seesion_type=args.type)
