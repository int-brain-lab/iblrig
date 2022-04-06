#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Monday, December 2nd 2019, 4:52:40 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
import logging
from pathlib import Path

import iblrig.misc as misc
import iblrig.path_helper as ph
import iblrig.raw_data_loaders as raw

log = logging.getLogger("iblrig")

IBLRIG_DATA_PATH = Path(ph.get_iblrig_data_folder())


def main():
    passive_sessions = list(IBLRIG_DATA_PATH.rglob("passive_data_for_ephys.flag"))

    # For each passive session found look into passiveSettings to find ephysSession name
    # search for the ephys session session in the rglobbed ephys sessions
    # If you find it just rename and move the folder raw_behavior_data -> raw_passive_data,
    # If no find search specifically for that session from the metadata and try to copy the folder
    # If folder exists throw an error
    log.info(f"Found {len(passive_sessions)} sessions in {IBLRIG_DATA_PATH}")
    for ps in passive_sessions:
        try:
            sett = raw.load_settings(str(ps.parent))
            esess = sett["CORRESPONDING_EPHYS_SESSION"]
            if not esess or esess is None:
                log.warning("Corresponding ephys session NOT FOUND in settings - data not moved")
                return
            if not Path(esess).exists():
                log.warning(f"Ephys session {esess}: NOT FOUND on filesystem - data not moved")
                return
            # Fails if dst_folder exists!
            misc.transfer_folder(
                str(ps.parent / "raw_behavior_data"),
                str(Path(esess) / "raw_passive_data"),
                force=False,
            )
            log.info(f"Moved passive data to {esess}")
            ps.unlink()
        except BaseException as e:
            log.warning(f"{e}\n Failed to move passive session {ps.parent}")


if __name__ == "__main__":
    main()
