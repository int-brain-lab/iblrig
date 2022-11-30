import argparse
import logging
import os
import traceback

from iblrig import path_helper
from iblrig.poop_count import poop

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
        log.info("Creating Alyx session...")
        here = os.getcwd()
        os.chdir(path_helper.get_iblrig_path() / "scripts" / "ibllib")
        os.system(f"python register_session.py {str(path_helper.get_iblrig_local_data_path())}")
        os.chdir(here)
        log.info("Completed registering session on Alyx.")

    except BaseException:
        log.error(traceback.format_exc())
        log.warning("Failed to register session on Alyx, will try again from local server after transfer")
