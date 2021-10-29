#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: scripts/register_session.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Tuesday, September 28th 2021, 3:03:38 pm
from ibllib.oneibl.registration import RegistrationClient
import sys
import traceback
import logging
_logger = logging.getLogger('ibllib')

if __name__ == "__main__":
    IBLRIG_DATA = sys.argv[1]
    try:
        RegistrationClient(one=None).create_sessions(IBLRIG_DATA, dry=False)
    except BaseException as e:
        _logger.error(traceback.format_exc())
        _logger.error("\n\nFailed to create session, will try again from local server after transfer...")

