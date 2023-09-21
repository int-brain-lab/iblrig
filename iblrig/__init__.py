from pathlib import Path
from setuptools_scm import get_version
from importlib.metadata import version

if Path(__file__).parents[1].joinpath('.github').exists():
    __version__ = get_version(version_scheme='post-release', local_scheme='dirty-tag')
else:
    __version__ = version('iblrig')
