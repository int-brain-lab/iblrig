# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 4:12:19 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 31-01-2019 04:12:21.2121
import tkinter as tk
from tkinter import simpledialog
from pathlib import Path
from ibllib.io import raw_data_loaders as raw
import shutil

IBLRIG_DATA = Path(__file__).parent.parent / 'iblrig_data' / 'Subjects'


def patch_settings_file(session_path: str, patch: dict) -> None:
    settings = raw.load_settings(session_path)
    settings.update(patch)
    sett_file = Path(session_path) / 'raw_behavior_data' / \
        '_iblrig_taskSettings.raw.json'
    with open(sett_file, 'w') as f:
            f.write(json.dumps(settings, indent=1))
            f.write('\n')

    return


def numinput(title, prompt, default=None, minval=None, maxval=None):
    root = tk.Tk()
    root.withdraw()
    ans = simpledialog.askinteger(
        title, prompt, initialvalue=default, minvalue=minval, maxvalue=maxval)
    if ans == 0:
        return ans
    elif not ans:
        return numinput(
            title, prompt, default=default, minval=minval, maxval=maxval)
    return


def main() -> None:
    poop_flags = list(IBLRIG_DATA.rglob('poop_count.flag'))

    if len(poop_flags) != 1:
        print('Too many or no poop flags found... exiting')
        return

    flag = poop_flags[0]

    poop_count = numinput('Poop up window', 'Enter poop pellet count')
    patch = {'POOP_COUNT': poop_count}
    patch_settings_file(str(flag.parent), patch)
    flag.unlink()

if __name__ == "__main__":
    main()
    # IBLRIG_DATA = '/home/nico/Projects/IBL/IBL-github/iblrig/scratch/test_iblrig_data/Subjects'
    # IBLRIG_DATA = Path(IBLRIG_DATA)
    print('.')
