#!/usr/bin/env python
# @Author: Niccolò Bonacchi & Michele Fabbri
# @Date: 2022-01-24
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
