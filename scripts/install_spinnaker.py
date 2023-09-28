import sys
import os
import subprocess
from importlib.util import find_spec
import zipfile
from pathlib import Path

from one.webclient import AlyxClient, http_download_file
from iblutil.io import hashfile


def download(asset: int, filename: str, target_md5: str):
    out_dir = Path.home().joinpath('Downloads')
    out_file = out_dir.joinpath(filename)
    options = {'target_dir': out_dir, 'clobber': True, 'return_md5': True}
    if out_file.exists() and hashfile.md5(out_file) == target_md5:
        return out_file
    try:
        tmp_file, md5_sum = AlyxClient().download_file(f'resources/spinnaker/{filename}', **options)
    except OSError as e1:
        try:
            url = f'https://flir.netx.net/file/asset/{asset}/original/attachment'
            tmp_file, md5_sum = http_download_file(url, **options)
        except OSError as e2:
            raise e2 from e1
    finally:
        os.rename(tmp_file, out_file)
        if md5_sum != target_md5:
            raise Exception(f'`{filename}` does not match the expected MD5 - please download to {out_dir} manually.')
        return out_file


if os.name != 'nt':
    raise Exception(f'{Path(__file__).name} can only be run on Windows.')

if find_spec('PySpin'):
    print('Python Spinnaker SDK is already installed')
else:
    if sys.base_prefix == sys.prefix:
        raise Exception('You need to be in the IBLRIG venv in order to install the Python Spinnaker SDK.')
    print('Installing Python Spinnaker SDK')
    file_zip = download(54396, 'spinnaker_python-3.1.0.79-cp310-cp310-win_amd64.zip', 'e00148800757d0ed7171348d850947ac')
    with zipfile.ZipFile(file_zip, 'r') as f:
        file_whl = f.extract(file_zip.stem + '.whl', file_zip.parent)
    subprocess.check_call([sys.executable, "-m", "pip", "install", file_whl])
    os.unlink(file_whl)
    file_zip.unlink()

file_winsdk = download(54386, 'SpinnakerSDK_FULL_3.1.0.79_x64.exe', 'd9d83772f852e5369da2fbcc248c9c81')
