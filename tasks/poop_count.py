# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 4:12:19 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 31-01-2019 04:12:21.2121
from pathlib import Path
from ibllib.io import raw_data_loaders as raw
from ibllib.graphic import numinput
import json
import ciso8601

IBLRIG_DATA = Path().cwd().parent.parent.parent.parent / 'iblrig_data' / 'Subjects'  # noqa


def patch_settings_file(sess_or_file: str, patch: dict) -> None:
    sess_or_file = Path(sess_or_file)
    if sess_or_file.is_file() and sess_or_file.name.endswith('_iblrig_taskSettings.raw.json'):  # noqa
        session = sess_or_file.parent.parent
        file = sess_or_file
    elif sess_or_file.is_dir() and sess_or_file.name.isdecimal():
        file = sess_or_file / 'raw_behavior_data' / '_iblrig_taskSettings.raw.json'  # noqa
        session = sess_or_file
    else:
        print('not a settings file or a session folder')
        return

    settings = raw.load_settings(session)
    settings.update(patch)
    with open(file, 'w') as f:
        f.write(json.dumps(settings, indent=1))
        f.write('\n')

    return


def main() -> None:
    poop_flags = list(IBLRIG_DATA.rglob('poop_count.flag'))
    poop_flags = sorted(poop_flags, key=lambda x: (
        ciso8601.parse_datetime(x.parent.parent.name), int(x.parent.name)))
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
    # IBLRIG_DATA = '/home/nico/Projects/IBL/IBL-github/iblrig/scratch/test_iblrig_data/Subjects'  # noqa
    # IBLRIG_DATA = Path(IBLRIG_DATA)
    # print('.')
