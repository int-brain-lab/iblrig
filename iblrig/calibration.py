from pathlib import Path

from iblrig.frame2ttl2 import Frame2TTL
import iblrig.base_tasks


file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
hw_settings = iblrig.path_helper.load_settings_yaml(file_settings)
screen = hw_settings["device_screen"]["DISPLAY_IDX"]

f2ttl = Frame2TTL(hw_settings["device_frame2ttl"]["COM_F2TTL"])
white = f2ttl.calibration(color=(255, 255, 255), screen=screen)
black = f2ttl.calibration(color=(0, 0, 0), screen=screen)
f2ttl.close()

pass
