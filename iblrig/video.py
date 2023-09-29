import sys
import os
import subprocess
from importlib.util import find_spec
import zipfile
from pathlib import Path
from shutil import which

from one.webclient import AlyxClient, http_download_file
from iblutil.io import hashfile


def spinnaker_sdk_installed() -> bool:
    if os.name != 'nt':
        return False
    spin_exe = which('SpinUpdateConsole_v140')
    return spin_exe and Path(spin_exe).parents[2].joinpath('src').exists()


def pyspin_installed() -> bool:
    return find_spec('PySpin') is not None


def pyspin_functional() -> bool:
    return spinnaker_sdk_installed() and pyspin_installed()


def install_spinnaker_sdk():
    def download(asset: int, filename: str, target_md5: str):
        print(f'Downloading {filename} ...')
        out_dir = Path.home().joinpath('Downloads')
        out_file = out_dir.joinpath(filename)
        options = {'target_dir': out_dir, 'clobber': True, 'return_md5': True}
        if out_file.exists() and hashfile.md5(out_file) == target_md5:
            return out_file
        try:
            tmp_file, md5_sum = AlyxClient().download_file(f'resources/spinnaker/{filename}', **options)
        except OSError as e1:
            try:
                url = f'https://flir.nsetx.net/file/asset/{asset}/original/attachment'
                tmp_file, md5_sum = http_download_file(url, **options)
            except OSError as e2:
                raise e2 from e1
        os.rename(tmp_file, out_file)
        if md5_sum != target_md5:
            raise Exception(f'`{filename}` does not match the expected MD5 - please try running the script again or')
        return out_file

    # Check prerequisites
    if os.name != 'nt':
        raise Exception(f'{Path(__file__).name} can only be run on Windows.')
    if sys.base_prefix == sys.prefix:
        raise Exception(f'{Path(__file__).name} needs to be started in the IBLRIG venv.')

    # Display some information
    print('This script will try to automatically\n'
          '   1) Download & install Spinnaker SDK for Windows, and\n'
          '   2) Download & install PySpin to the IBLRIG Python environment.')
    input('Press [ENTER] to continue.\n')

    # Download & install Spinnaker SDK
    if spinnaker_sdk_installed():
        print('Spinnaker SDK for Windows is already installed.')
    else:
        file_winsdk = download(54386, 'SpinnakerSDK_FULL_3.1.0.79_x64.exe', 'd9d83772f852e5369da2fbcc248c9c81')
        print('Installing Spinnaker SDK for Windows ...')
        input('Please select the "Application Development" Installation Profile. Everything else can be left at '
              'default values. Press [ENTER] to continue.')
        return_code = subprocess.check_call(file_winsdk)
        if return_code == 0 and spinnaker_sdk_installed():
            print('Installation of Spinnaker SDK was successful.')
        os.unlink(file_winsdk)

    # Download & install PySpin
    if pyspin_installed():
        print('PySpin is already installed.')
    else:
        file_zip = download(54396, 'spinnaker_python-3.1.0.79-cp310-cp310-win_amd64.zip',
                            'e00148800757d0ed7171348d850947ac')
        print('Installing PySpin ...')
        with zipfile.ZipFile(file_zip, 'r') as f:
            file_whl = f.extract(file_zip.stem + '.whl', file_zip.parent)
        return_code = subprocess.check_call([sys.executable, "-m", "pip", "install", file_whl])
        if return_code == 0:
            print('Installation of PySpin was successful.')
        os.unlink(file_whl)
        file_zip.unlink()
