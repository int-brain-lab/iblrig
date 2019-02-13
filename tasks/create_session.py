# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 1:15:46 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 31-01-2019 01:15:49.4949
from pathlib import Path
import argparse
import ibllib.io.params as params
import oneibl.params
from alf.one_iblrig import create
from poop_count import main as poop

IBLRIG_DATA = Path().cwd().parent.parent.parent.parent / 'iblrig_data' / 'Subjects'  # noqa


def main():
    pfile = Path(params.getfile('one_params'))
    if not pfile.exists():
        oneibl.params.setup_alyx_params()

    create(IBLRIG_DATA, dry=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create session in Alyx')
    parser.add_argument(
        '--patch', help='Ask for a poop count before registering',
        required=False, default=True, type=bool)
    args = parser.parse_args()

    if args.patch:
        poop()
        main()
    else:
        main()

    print('done')
