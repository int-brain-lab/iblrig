# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 18th 2019, 2:45:32 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 18-01-2019 02:45:34.3434
from pathlib import Path
from typing import List
import logging

log = logging.getLogger('iblrig')


def find_subjects_folder(folder: Path) -> Path:
    # Try to find Subjects folder one level
    if folder.name.lower() != 'subjects':
        log.info(f"Looking for 'Subjects' folder in '{folder}'")
        # Try to find Subjects folder if folder.glob
        spath = [x for x in folder.glob('*') if x.name.lower() == 'subjects']
        if not spath:
            log.error(
                f"Couldn't find 'Subjects' folder in '{folder.name}'")
            raise(ValueError)
        elif len(spath) > 1:
            log.error(
                f"Too many 'Subjects' folders: '{spath}''")
            raise(ValueError)
        else:
            folder = folder / spath[0]

    log.info(f"Found 'Subjects' folder: '{Path(*folder.parts[-2:])}'")

    return folder


def find_sessions(folder: str or Path) -> List[Path]:
    # Ensure folder is a Path object
    if not isinstance(folder, Path):
        folder = Path(folder)

    folder = find_subjects_folder(folder)
    # Glob all mouse fodlers
    mouse_folders = [x for x in folder.glob('*') if x.is_dir()]
    if not mouse_folders:
        log.error(f"No subjects found in '{Path(*folder.parts[-2:])}'")
        raise(ValueError)
    log.info(f"Found '{len(list(mouse_folders))}' subjects: {[x.name for x in mouse_folders]}")
    # Glob all dates
    dates = [x for mouse in mouse_folders for x in mouse.glob(
        '*') if x.is_dir()]
    log.info(f"Found '{len(dates)}' dates: {[x.name for x in dates]}")
    # Glob all sessions
    sessions = [y for x in dates for y in x.glob('*') if y.is_dir()]
    # Ensure sessions have files
    sessions = list(
        {p.parent for f in sessions for p in f.glob('*') if p.is_file()})
    log.info(f"Found '{len(sessions)}' sessions: {[str(Path(*x.parts[-3:])) for x in sessions]}")
    sessions = [str(x) for x in sessions]

    return sessions


def remove_empty_folders(folder: str or Path) -> None:
    all_folders = [x for x in Path(folder).rglob('*') if x.is_dir()]
    for f in all_folders:
        try:
            f.rmdir()
            log.info(f"Empty folder removed: {str(Path(*f.parts[-3:]))}")
        except:
            log.debug("Skipping", str(Path(*f.parts[-3:])))
            continue


def get_sessions(folder: str or Path,
                 pattern: str = '') -> List[str]:
    sessions = find_sessions(folder)
    matches = []
    for s in sessions:
        x = Path(s)
        matches.extend(x.rglob(pattern))
        print(str(s))

    matches = list(set(str(x.parent) for x in matches))
    return matches


if __name__ == "__main__":
    folder = Path(
        "/home/nico/Projects/IBL/IBL-github/iblrig/scratch/test_iblrig_data")

    sessions = find_sessions(folder)
    sessions = find_sessions(folder / 'Subjects')
    remove_empty_folders(folder)
    t_sessions = get_sessions(folder, pattern='create*')
    print(t_sessions)

    print('.')
