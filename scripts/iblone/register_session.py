#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Tuesday, September 28th 2021, 3:03:38 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
import logging
import sys
import traceback

from ibllib.oneibl.registration import RegistrationClient

log = logging.getLogger("iblrig")


if __name__ == "__main__":
    IBLRIG_DATA = sys.argv[1]
    try:
        log.info("Trying to register session in Alyx...")
        RegistrationClient(one=None).create_sessions(IBLRIG_DATA, dry=False)
        log.info("Done")
    except Exception:
        log.error(traceback.format_exc())
        log.warning(
            "Failed to register session on Alyx, will try again from local server after transfer",
        )
