#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 1:15:46 pm
import argparse
from pathlib import Path
import os

from ibllib.oneibl.registration import RegistrationClient

from iblrig.poop_count import poop
from iblrig import envs

IBLRIG_FOLDER = Path(__file__).absolute().parent.parent
IBLRIG_DATA = IBLRIG_FOLDER.parent / "iblrig_data" / "Subjects"  # noqa
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"


def main():
    RegistrationClient(one=None).create_sessions(IBLRIG_DATA, dry=False)


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
    try:
        python = envs.get_env_python(env_name="ibllib")
        here = os.getcwd()
        os.chdir(os.path.join(IBLRIG_FOLDER, "scripts"))
        os.system(f"{python} register_session.py {IBLRIG_DATA}")
        os.chdir(here)

    except BaseException as e:
        print(
            e, "\n\nFailed to create session, will try again from local server after transfer...",
        )
