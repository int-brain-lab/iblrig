#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 11th 2019, 2:04:42 pm
# 4 ibllib misc
import logging

from ibllib.misc import logger_config

USE_LOGGING = True
LOGLEVEL = logging.INFO
if USE_LOGGING:
    log = logger_config(name='iblrig')
    log.setLevel(LOGLEVEL)
else:
    # deactivate all log calls for use as a library
    logging.getLogger('iblrig').addHandler(logging.NullHandler())
