from pathlib import Path
from shutil import which

BASE_DIR = str(Path(__file__).parents[1])
IS_GIT = Path(BASE_DIR).joinpath('.git').exists() and which('git') is not None
