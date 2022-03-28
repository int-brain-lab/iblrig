#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Thursday, January 31st 2019, 1:15:46 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
import argparse
import logging
import os
import traceback

from iblrig import envs
from iblrig.poop_count import poop
import iblrig.path_helper as ph


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
        print("Creating session from ibllib environment...")
        python = envs.get_env_python(env_name="ibllib")
        here = os.getcwd()
        os.chdir(os.path.join(ph.get_iblrig_folder(), "scripts", "ibllib"))
        os.system(f"{python} register_session.py {ph.get_iblrig_data_folder()}")
        os.chdir(here)

    except BaseException:
        log.error(traceback.format_exc())
        log.warning(
            "Failed to register session on Alyx, will try again from local server after transfer",
        )
