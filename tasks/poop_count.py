#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 4:12:19 pm
from pathlib import Path
from ibllib.graphic import numinput
from dateutil import parser
from misc import patch_settings_file

IBLRIG_DATA = Path().cwd().parent.parent.parent.parent / 'iblrig_data' / 'Subjects'  # noqa


def main() -> None:
    poop_flags = list(IBLRIG_DATA.rglob('poop_count.flag'))
    poop_flags = sorted(poop_flags, key=lambda x: (
        parser.parse(x.parent.parent.name), int(x.parent.name)))
    if not poop_flags:
        return
    flag = poop_flags[-1]
    session_name = '/'.join(flag.parent.parts[-3:])
    poop_count = numinput(
        'Poop up window',
        f'Enter poop pellet count for session: \n{session_name}')
    patch = {'POOP_COUNT': poop_count}
    patch_settings_file(str(flag.parent), patch)
    flag.unlink()


if __name__ == "__main__":
    main()
    # IBLRIG_DATA = '/home/nico/Projects/IBL/github/iblrig/scratch/test_iblrig_data/Subjects'  # noqa
    # IBLRIG_DATA = Path(IBLRIG_DATA)
    # print('.')
