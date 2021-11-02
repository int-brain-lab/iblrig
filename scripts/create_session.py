#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 1:15:46 pm
import argparse
import logging
import os
import traceback
from pathlib import Path

from iblrig import envs
from iblrig.poop_count import poop

_logger = logging.getLogger('ibllib')
IBLRIG_FOLDER = Path(__file__).absolute().parent.parent
IBLRIG_DATA = IBLRIG_FOLDER.parent / "iblrig_data" / "Subjects"  # noqa
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"
log = logging.getLogger("iblrig")


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

    except BaseException:
        log.error(traceback.format_exc())
        log.warning(
            "Failed to register session on Alyx, will try again from local server after transfer",
        )
