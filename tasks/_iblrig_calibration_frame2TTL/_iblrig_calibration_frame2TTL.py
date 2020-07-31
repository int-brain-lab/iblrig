import datetime
import logging
import time

import iblrig.params as params
import iblrig.alyx as alyx
import task_settings
import user_settings
from iblrig.frame2TTL import Frame2TTL
from session_params import SessionParamHandler

log = logging.getLogger("iblrig")

sph = SessionParamHandler(task_settings, user_settings)
f2ttl = Frame2TTL(sph.PARAMS["COM_F2TTL"])

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

    patch = {
        "COM_F2TTL": f2ttl.serial_port,
        "F2TTL_DARK_THRESH": f2ttl.recomend_dark,
        "F2TTL_LIGHT_THRESH": f2ttl.recomend_light,
        "F2TTL_CALIBRATION_DATE": datetime.datetime.now().date().isoformat(),
    }

    params.update_params_file(data=patch)
    alyx.update_alyx_params(data=patch)

sph.stop_screen_color()

print("Done")
