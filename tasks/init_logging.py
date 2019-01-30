# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 11th 2019, 2:04:42 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 11-01-2019 02:06:06.066
# 4 ibllib misc
from ibllib.misc import logger_config
import logging
USE_LOGGING = True
LOGLEVEL = logging.INFO
if USE_LOGGING:
    log = logger_config(name='iblrig')
    log.setLevel(LOGLEVEL)

else:
    # deactivate all log calls for use as a library
    logging.getLogger('iblrig').addHandler(logging.NullHandler())
