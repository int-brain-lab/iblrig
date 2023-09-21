from pathlib import Path
from iblrig import __file__ as IBLRIG_INIT_FILE

BASE_DIR = Path(IBLRIG_INIT_FILE).parents[1]
IS_GIT = BASE_DIR.joinpath('.git').exists()
