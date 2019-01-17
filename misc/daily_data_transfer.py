# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, January 16th 2019, 2:03:59 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 16-01-2019 02:04:01.011
import datetime
import shutil
import sys
from pathlib import Path


def main(local_folder: str, remote_folder: str, day: str = None) -> None:
    if day is None:
        day = datetime.datetime.now().date().isoformat()
    local_folder = Path(local_folder) / "Subjects"
    remote_folder = Path(remote_folder) / "Subjects"

    # Get all date folders of today
    todays_sessions = []
    for subject in local_folder.glob("*"):
        todays_sessions.extend([x for x in subject.glob("*") if day in x.name])

    # Get all session paths for today
    all_sessions = []
    for session in todays_sessions:
        all_sessions.extend(session.glob("*"))

    # Find all sessions that have "transfer_me.flag"
    src_session_paths = []
    for s in all_sessions:
        src_session_paths.extend(
            [s for x in s.glob("*") if "transfer_me.flag" in x.name])

    # Create all dst paths
    dst_session_paths = []
    for s in src_session_paths:
        mouse = s.parts[-3]
        date = s.parts[-2]
        sess = s.parts[-1]
        d = remote_folder / mouse / date / sess
        dst_session_paths.append(d)

    for src, dst in zip(src_session_paths, dst_session_paths):
        shutil.copytree(src, dst)


if __name__ == "__main__":
    # local_folder = "/home/nico/Projects/IBL/IBL-github/iblrig/scratch/test_iblrig_data"
    # remote_folder = "/home/nico/Projects/IBL/IBL-github/iblrig/scratch/test_iblrig_data_on_server"
    if len(sys.argv == 3):
        main(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 4:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
