#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Friday, January 11th 2019, 2:04:42 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
"""
Configuration for logging
"""
import logging

from iblrig.misc import logger_config

USE_LOGGING = True
LOGLEVEL = logging.INFO
if USE_LOGGING:
    log = logger_config(name="iblrig")
    log.setLevel(LOGLEVEL)
else:
    # deactivate all log calls for use as a library
    logging.getLogger("iblrig").addHandler(logging.NullHandler())
