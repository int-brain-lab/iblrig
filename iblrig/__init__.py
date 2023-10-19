# PLEASE REMEMBER TO:
# 1) update CHANGELOG.md including changes from the last tag
# 2) Pull request to iblrigv8dev
# 3) Check CI and eventually wet lab test
# 4) Pull request to iblrigv8
# 5) git tag the release in accordance to the version number below (after merge!)
__version__ = '8.11.2'

# The following method call will try to get post-release information (i.e. the number of commits since the last tagged
# release corresponding to the one above), plus information about the state of the local repository (dirty/broken)
from iblrig.version_management import get_detailed_version_string
__version__ = get_detailed_version_string(__version__)
