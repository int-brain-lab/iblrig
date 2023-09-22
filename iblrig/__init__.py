from setuptools_scm import get_version
from pathlib import Path
from importlib import metadata

__version__ = get_version(root='..', relative_to=__file__, version_scheme="post-release", local_scheme="dirty-tag",
                          fallback_version=metadata.version('iblrig'), write_to=Path('iblrig', '_version.py'))
