import logging
from pathlib import Path

from one.alf.files import session_path_parts
from ibllib.io.raw_data_loaders import patch_settings

import iblrig.misc as misc
import iblrig.raw_data_loaders as raw
from iblrig import path_helper

log = logging.getLogger("iblrig")

IBLRIG_DATA_PATH = path_helper.get_iblrig_local_data_path()


def main():
    passive_sessions = list(IBLRIG_DATA_PATH.rglob("passive_data_for_ephys.flag"))

    # For each passive session found look into passiveSettings to find ephysSession name
    # search for the ephys session in the rglobbed ephys sessions
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
            parts = session_path_parts(esess, as_dict=True, assert_valid=True)
            parts.pop('lab')
            patch_settings(
                esess, collection='raw_passive_data', new_collection='raw_passive_data', **parts)
            log.info(f"Moved passive data to {esess}")
            ps.unlink()
        except BaseException as e:
            log.warning(f"{e}\n Failed to move passive session {ps.parent}")


if __name__ == "__main__":
    main()
