import platform
from glob import glob
from pathlib import Path
# from serial import Serial

import logging
import numpy as np


import iblrig.base_tasks
# from pybpodapi.protocol import Bpod, StateMachine


# set up logging
logging.basicConfig(
    format="%(levelname)-8s %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# read hardware_settings.yaml
log.info('Checking hardware_settings.yaml:')
file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
hw_settings = iblrig.path_helper.load_settings_yaml(file_settings)

# collect all port-strings
ports = [d for d in hw_settings.values() if isinstance(d, dict)]
ports = {k: v for x in ports for k, v in x.items() if k[0:4].startswith('COM_')}

# check for undefined serial ports (warn only)
tmp = [(k, v) for k, v in ports.items() if v is None]
for p in tmp:
    log.warning("- {} is undefined (OK if you don't want to use it)".format(p[0]))
if not any(tmp):
    log.info('- no undefined serial ports found')
ports = {k: v for k, v in ports.items() if v is not None}

# check for duplicate serial ports
tmp = np.unique(list(ports.values()), return_counts=True)[1] > 1
if any(tmp):
    raise Exception('Duplicate serial port: "{}"'.format(list(ports.values())[np.argmax(tmp > 1)]))
else:
    log.info('- no duplicate serial ports found')

# check for invalid serial ports
match platform.system():
    case 'Windows':
        valid_ports = ['COM{:d}'.format(i + 1) for i in range(256)]
    case 'Linux':
        valid_ports = glob('/dev/tty[A-Za-z]*')
    case _:
        raise Exception('Unsupported platform: "{}"'.format(platform.system()))
for p in [(k, v) for k, v in ports.items() if v not in valid_ports]:
    raise Exception('Invalid serial port: "{}"'.format(p[1]))
log.info('- no invalid serial ports found')

# TO DO: test correct assignment of serial ports

# TO DO: bpod
# bpod = Bpod(hw_settings['device_bpod']['COM_BPOD'])
# bpod.close()

# TO DO: order of modules
# TO DO: BNC connections
# TO DO: camera
# TO DO: sound output
# TO DO: encoder module
# TO DO: ambient module
# TO DO:

log.info('---------------')
log.info('No issues found')
