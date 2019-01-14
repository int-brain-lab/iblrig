# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, January 11th 2019, 2:04:42 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 11-01-2019 02:06:06.066
import platform
import logging
USE_LOGGING = True
#%(asctime)s,%(msecs)d
if USE_LOGGING:
    level = '%(levelname)-4s '
    fname = '[%(filename)s:%(lineno)d] '
    mstime = '%(asctime)s,%(msecs)d\n'
    msg = '        %(message)s\n'
    log_format = level + fname + mstime + msg

    logging.basicConfig(format=log_format, datefmt='%Y-%m-%dT%H:%M:%S')
    # add some colours for an easier log experience
    if platform == 'linux':
        logging.addLevelName(
            logging.DEBUG,
            "\033[0;34m%s\033[0;0m" % logging.getLevelName(logging.DEBUG))
        logging.addLevelName(
            logging.INFO,
            "\033[0;37m%s\033[0;0m" % logging.getLevelName(logging.INFO))
        logging.addLevelName(
            logging.WARNING,
            "\033[0;33m%s\033[0;0m" % logging.getLevelName(logging.WARNING))
        logging.addLevelName(
            logging.ERROR,
            "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
        logging.addLevelName(
            logging.CRITICAL,
            "\033[1;35m%s\033[1;0m" % logging.getLevelName(logging.CRITICAL))

    logger = logging.getLogger('iblrig').setLevel(logging.INFO)

else:
    # deactivate all log calls for use as a library
    logging.getLogger('iblrig').addHandler(logging.NullHandler())
