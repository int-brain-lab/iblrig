#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Friday, May 17th 2019, 9:21:19 am
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
"""
Various interaction with user and session forms
"""
import logging

import iblrig.graphic as graph
from iblrig.misc import patch_settings_file

log = logging.getLogger("iblrig")


def ask_subject_weight(subject: str, settings_file_path: str = None) -> float:
    out = graph.numinput("Subject weighing (gr)", f"{subject} weight (gr):", nullable=False)
    log.info(f"Subject weight {out}")
    if settings_file_path is not None:
        patch = {"SUBJECT_WEIGHT": out}
        patch_settings_file(settings_file_path, patch)
    return out


def ask_session_delay() -> int:
    out = graph.numinput(
        "Session delay",
        "Delay session initiation by (min):",
        default=0,
        minval=0,
        maxval=60,
        nullable=False,
        askint=True,
    )
    out = out * 60
    return out


def ask_is_mock(settings_file_path: str = None) -> bool:
    out = None
    resp = graph.strinput(
        "Session type", "IS this a MOCK recording? (yes/NO)", default="NO", nullable=True,
    )
    if resp is None:
        return ask_is_mock(settings_file_path)
    if resp.lower() in ["no", "n", ""]:
        out = False
    elif resp.lower() in ["yes", "y"]:
        out = True
    else:
        return ask_is_mock(settings_file_path)
    if settings_file_path is not None and out is not None:
        patch = {"IS_MOCK": out}
        patch_settings_file(settings_file_path, patch)
    return out


def ask_confirm_session_idx(session_idx):
    # Confirm this is the session to load with user. If not override SESSION_IDX
    sess_num = int(session_idx + 1)
    sess_num = graph.numinput(
        "Confirm pregenerated session to load",
        "Load trial sequence for recording day number:",
        default=sess_num,
        askint=True,
        minval=1,
    )
    if sess_num != session_idx + 1:
        session_idx = sess_num - 1
    return session_idx
