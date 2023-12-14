from pathlib import Path
from shutil import which

BASE_PATH = Path(__file__).parents[1]
BASE_DIR = str(BASE_PATH)
IS_GIT = Path(BASE_DIR).joinpath('.git').exists() and which('git') is not None
BONSAI_EXE = BASE_PATH.joinpath('Bonsai', 'Bonsai.exe')
SETTINGS_PATH = BASE_PATH.joinpath('settings')
HARDWARE_SETTINGS_YAML = SETTINGS_PATH.joinpath('hardware_settings.yaml')
RIG_SETTINGS_YAML = SETTINGS_PATH.joinpath('iblrig_settings.yaml')
