import os
from importlib.util import find_spec
from pathlib import Path
from shutil import which

BASE_PATH = Path(__file__).parents[1]
BASE_DIR = str(BASE_PATH)
IS_GIT = Path(BASE_DIR).joinpath('.git').exists() and which('git') is not None
BONSAI_EXE = BASE_PATH.joinpath('Bonsai', 'Bonsai.exe')
SETTINGS_PATH = BASE_PATH.joinpath('settings')
HARDWARE_SETTINGS_YAML = SETTINGS_PATH.joinpath('hardware_settings.yaml')
RIG_SETTINGS_YAML = SETTINGS_PATH.joinpath('iblrig_settings.yaml')
HAS_SPINNAKER = (
    os.name == 'nt'
    and (_spin_exe := which('SpinUpdateConsole_v140')) is not None
    and Path(_spin_exe).parents[2].joinpath('src').exists()
)
HAS_PYSPIN = find_spec('PySpin') is not None
PYSPIN_AVAILABLE = HAS_SPINNAKER and HAS_PYSPIN
