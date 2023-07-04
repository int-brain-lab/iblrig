from pathlib import Path

from setuptools import setup, find_packages

PYTHON_REQUIRES = ">=3.10"  # python version requirement
LONG_DESCRIPTION = "Software used to interact with various pieces of specialized hardware for neuroscience data acquisition."

with open("requirements.txt") as f:
    require = [x.strip() for x in f.readlines() if not x.startswith("git+")]


def read(rel_path):
    here = Path(__file__).parent.absolute()
    with open(here.joinpath(rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setup(
    name="iblrig",
    version=get_version(Path("iblrig").joinpath("__init__.py")),
    python_requires=PYTHON_REQUIRES,
    description="IBL libraries",
    license="MIT",
    long_description=LONG_DESCRIPTION,
    author="IBL Staff",
    url="https://www.internationalbrainlab.com/",
    packages=find_packages(exclude=["scratch"]),  # same as name
    # external packages as dependencies
    install_requires=require,
    scripts=[],
    entry_points={
        'console_scripts': [
            'viewsession=iblrig.commands:viewsession',
            'transfer_data=iblrig.commands:transfer_data'],
    },
)
