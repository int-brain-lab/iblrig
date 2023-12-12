from pathlib import Path
from shutil import which

BASE_PATH = Path(__file__).parents[1]
BASE_DIR = str(BASE_PATH)
IS_GIT = Path(BASE_DIR).joinpath('.git').exists() and which('git') is not None
