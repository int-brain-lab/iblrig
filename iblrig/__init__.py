__version__ = "6.6.4"
import logging

import colorlog

# Configurations for colorlog formatting
format_str = "%(asctime)s.%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"
cformat = "%(log_color)s" + format_str
colors = {
    "DEBUG": "green",
    "INFO": "cyan",
    "WARNING": "bold_yellow",
    "ERROR": "bold_red",
    "CRITICAL": "bold_purple",
}
formatter = colorlog.ColoredFormatter(cformat, date_format, log_colors=colors)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

# Configurations for iblrig logging
log_conf = logging.getLogger("iblrig")
log_conf.setLevel(logging.INFO)
log_conf.addHandler(stream_handler)
