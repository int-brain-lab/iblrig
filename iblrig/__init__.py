# PLEASE REMEMBER TO:
# 1) update CHANGELOG.md
# 2) git tag the release in accordance to the version number below (after merge!)
__version__ = '8.9.4'

# The following method call will try to get post-release information (i.e. the number of commits since the last tagged
# release corresponding to the one above), plus information about the state of the local repository (dirty/broken)
from iblrig.version_management import get_detailed_version_string
__version__ = get_detailed_version_string(__version__)
