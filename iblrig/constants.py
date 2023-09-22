from pathlib import Path

BASE_DIR = str(Path(__file__).parents[1])
IS_GIT = Path(BASE_DIR).joinpath('.git').exists()
