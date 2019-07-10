import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler
from pathlib import Path


task_settings.IBLRIG_FOLDER = Path(__file__).parent.parent.parent

sph = SessionParamHandler(task_settings, user_settings)

sph.start_screen_color()

sph.OSC_CLIENT.send_message('/r', 255)
sph.OSC_CLIENT.send_message('/g', 255)
sph.OSC_CLIENT.send_message('/b', 255)
import time
time.sleep(1)
sph.OSC_CLIENT.send_message('/r', 0)
sph.OSC_CLIENT.send_message('/g', 0)
sph.OSC_CLIENT.send_message('/b', 0)
# sph.f2ttl.suggest_thresholds()
# sph.update_board_params()
print('Done')
