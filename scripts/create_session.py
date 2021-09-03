#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 1:15:46 pm
import argparse
from pathlib import Path

import ibllib.io.params as params
import one.params
# from ibllib.pipes.experimental_data import create
from oneibl.registration import RegistrationClient

from iblrig.poop_count import poop

IBLRIG_FOLDER = Path(__file__).absolute().parent.parent
IBLRIG_DATA = IBLRIG_FOLDER.parent / "iblrig_data" / "Subjects"  # noqa
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"


def main():
    pfile = Path(params.getfile("one_params"))
    if not pfile.exists():
        one.params.setup()

    RegistrationClient(one=None).create_sessions(IBLRIG_DATA, dry=False)
    # create(IBLRIG_DATA, dry=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create session in Alyx")
    parser.add_argument(
        "--poop",
        help="Ask for a poop count before registering",
        required=False,
        default=True,
        type=bool,
    )
    args = parser.parse_args()

    if args.poop:
        poop()
        main()
    else:
        main()

    print("done")
