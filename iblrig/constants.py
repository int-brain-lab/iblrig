from pathlib import Path
from shutil import which

from iblrig.camera import pyspin_installed, spinnaker_sdk_installed

BASE_DIR = str(Path(__file__).parents[1])
IS_GIT = Path(BASE_DIR).joinpath('.git').exists() and which('git') is not None
HAS_PYSPIN = spinnaker_sdk_installed() and pyspin_installed()
