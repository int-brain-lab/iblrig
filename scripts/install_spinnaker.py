import sys
from hashlib import md5
from os import unlink
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path

from one.webclient import AlyxClient
from iblutil.io import hashfile


def download(asset: int, filename: str, target_md5: str):
    print(f'Downloading {filename}')
    out_file = Path.home().joinpath('Downloads', filename)
    # if Path(out_file).exists() and hashfile.md5(out_file) == target_md5:
    #     return out_file, True
    try:
        AlyxClient().download_file(f'resources/spinnaker/{filename}s', clobber=True,
                                   target_dir=Path.home().joinpath('Downloads'))
    except OSError as error_alyx:
        try:
            print('Couldn\'t download from Alyx - trying alternative (please wait)')
            url = f'https://flir.netx.net/file/asset/{asset}/original/attachment'
            with urllib.request.urlopen(url) as response, open(out_file, 'wb') as f:
                shutil.copyfileobj(response, f)
        except OSError as error_flir:
            raise error_flir from error_alyx
    finally:
        return out_file, hashfile.md5(out_file) == target_md5


out1 = download(54396, 'spinnaker_python-3.1.0.79-cp310-cp310-win_amd64.zip', 'e00148800757d0ed7171348d850947ac')
out2 = download(54386, 'SpinnakerSDK_FULL_3.1.0.79_x64.exe', 'd9d83772f852e5369da2fbcc248c9c81')
pass

# with zipfile.ZipFile(path_to_zip_file, 'r') as zip_ref:
#     zip_ref.extractall(directory_to_extract_to)


# return

# alyx.is_logged_in
# file_remote = 'resources/spinnaker/spinnaker_python-3.1.0.79-cp310-cp310-win_amd64.zip'
# file_local = alyx.download_file(file_remote)
# subprocess.check_call([sys.executable, "-m", "pip", "install", file_local])
# unlink(file_local)
