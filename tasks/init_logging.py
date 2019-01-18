# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 11th 2019, 2:04:42 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 11-01-2019 02:06:06.066
# 4 ibllib misc
from sys import platform
import logging
USE_LOGGING = True
#%(asctime)s,%(msecs)d
if USE_LOGGING:
    level = '\n%(levelname)-4s: '
    fname = '[%(processName)s:%(filename)s:%(lineno)d] '
    mstime = '%(asctime)s.%(msecs)d'
    msg = '%(message)s'
    spacer = '------> '

    if platform == 'win32':
        log_format = level + msg + '\n' + spacer + fname + mstime
        logging.basicConfig(format=log_format, datefmt='%Y-%m-%dT%H:%M:%S')
    elif platform == 'linux':
        RESET = "\033[0m"
        COLOR = "\033[1;%dm"
        BOLD = "\033[1m"
        log_format = BOLD + level + RESET + BOLD + msg + RESET + \
            '\n' + spacer + fname + mstime
        logging.basicConfig(format=log_format, datefmt='%Y-%m-%dT%H:%M:%S')
        BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
        COLORS = {
            'WARNING': YELLOW,
            'INFO': WHITE,
            'DEBUG': BLUE,
            'CRITICAL': YELLOW,
            'ERROR': RED
        }
        LEVELNAMES = {
            "DEBUG": logging.getLevelName(logging.DEBUG),
            "INFO": logging.getLevelName(logging.INFO),
            "WARNING": logging.getLevelName(logging.WARNING),
            "ERROR": logging.getLevelName(logging.ERROR),
            "CRITICAL": logging.getLevelName(logging.CRITICAL),
        }

        def coloredLevelName(levelname: str) -> str:
            out = COLOR % (30 + COLORS[levelname]) + \
                LEVELNAMES[levelname] + RESET

            return out
        # add some colours for an easier log experience
        logging.addLevelName(logging.DEBUG, coloredLevelName('DEBUG'))
            # "\033[0;34m%s\033[0;0m" % logging.getLevelName(logging.DEBUG))
        logging.addLevelName(logging.INFO, coloredLevelName('INFO'))
            # "\033[0;37m%s\033[0;0m" % logging.getLevelName(logging.INFO))
        logging.addLevelName(logging.WARNING, coloredLevelName('WARNING'))
            # "\033[0;33m%s\033[0;0m" % logging.getLevelName(logging.WARNING))
        logging.addLevelName(logging.ERROR, coloredLevelName('ERROR'))
            # "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
        logging.addLevelName(logging.CRITICAL, coloredLevelName('CRITICAL'))
            # "\033[1;35m%s\033[1;0m" % logging.getLevelName(logging.CRITICAL))

    logger = logging.getLogger('iblrig').setLevel(logging.INFO)

else:
    # deactivate all log calls for use as a library
    logging.getLogger('iblrig').addHandler(logging.NullHandler())
