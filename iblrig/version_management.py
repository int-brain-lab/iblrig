from packaging import version
from pathlib import Path
from re import sub
from subprocess import check_output, check_call, SubprocessError

import iblrig


def check_for_updates():

    # assert that git is being used
    dir_base = Path(iblrig.__file__).parents[1]
    if not dir_base.joinpath('.git').exists():
        return -1, ''

    # get newest remote tag
    try:
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=dir_base)
        branch = sub(r'\n', '', branch.decode())
        check_call(["git", "fetch", "origin", branch, "-q"], cwd=dir_base, timeout=5)
        version_remote_str = check_output(["git", "describe", "--tags", "--abbrev=0"],
                                          cwd=dir_base)
        version_remote_str = sub(r'[^\d\.]', '', version_remote_str.decode())
    except (SubprocessError, FileNotFoundError):
        return -1, ''

    # parse version information
    try:
        version_local = version.parse(iblrig.__version__)
        version_remote = version.parse(version_remote_str)
    except version.InvalidVersion:
        return -1, ''

    return version_remote > version_local, version_remote_str
