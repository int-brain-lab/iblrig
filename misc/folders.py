# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 18th 2019, 2:45:32 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 18-01-2019 02:45:34.3434
from pathlib import Path
from typing import TypeVar, List, Dict, Tuple
import logging
import tasks.init_logging as l
log = logging.getLogger('iblrig')


folder = Path(
    "/home/nico/Projects/IBL/IBL-github/iblrig/scratch/test_iblrig_data")

SP = TypeVar('SP', str, Path)


def find_sessions(folder: str or Path) -> List[Path]:
    # Ensure folder is a Path object
    if not isinstance(folder, Path):
        folder = Path(folder)
    # Try to find Subjects folder one level
    if folder.name.lower() is not 'subjects':
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
            log.info(f"'Subjects' folder found: '{Path(*folder.parts[-2:])}'")
    # Glob all subjects
    log.info(f"Loooking for mice in '{Path(*folder.parts[-2:])}'")
    subject_folders = list(folder.glob('*'))
    if not subject_folders:
        log.error(f"No subjects found in '{Path(*folder.parts[-2:])}'")
        raise(ValueError)
    log.info(f"Found '{len(list(subject_folders))}' subjects: {[x.name for x in subject_folders]}")
    # Glob all dates
    for subj in subject_folders:
        subj.glob('*')

    return subject_folders


find_sessions(folder)

folder.parents


bin(ord('N'))
