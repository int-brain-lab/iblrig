import json
import logging
import time
import datetime

import iblrig.alyx as alyx
import task_settings
import user_settings
from iblrig.frame2TTL import Frame2TTL, update_frame2ttl_params_file
from iblrig.path_helper import get_iblrig_params_folder
from session_params import SessionParamHandler

log = logging.getLogger('iblrig')

sph = SessionParamHandler(task_settings, user_settings)
f2ttl = Frame2TTL(sph.COM['FRAME2TTL'])

sph.start_screen_color()
sph.set_screen(rgb=[255, 255, 255])
time.sleep(1)
f2ttl.measure_white()
sph.set_screen(rgb=[0, 0, 0])
time.sleep(1)
f2ttl.measure_black()
resp = f2ttl.calc_recomend_thresholds()
if resp != -1:
    f2ttl.set_recommendations()

    patch = {'COM_F2TTL': f2ttl.serial_port,
             'F2TTL_DARK_THRESH': f2ttl.recomend_dark,
             'F2TTL_LIGHT_THRESH': f2ttl.recomend_light,
             'F2TTL_CALIBRATION_DATE': datetime.datetime.now().isoformat()}

    iblrig_params_folder = get_iblrig_params_folder()
    update_frame2ttl_params_file(data=patch)
    try:
        alyx.update_board_params(data=patch)
    except Exception as e:
        log.error(e)
        log.error("Unable to sync to Alyx, data was saved locally.")

sph.stop_screen_color()

print('Done')
