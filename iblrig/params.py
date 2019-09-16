#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, September 13th 2019, 2:57:40 pm
import logging
import iblrig.logging_  # noqa
from pathlib import Path
import iblrig.path_helper as path_helper
import json
from pybpodgui_api.models.project import Project

log = logging.getLogger('iblrig')


EMPTY_BOARD_PARAMS = {
    'NAME': None,  # str
    'COM_BPOD': None,  # str
    'COM_ROTARY_ENCODER': None,  # str
    'COM_F2TTL': None,  # str
    'F2TTL_DARK_THRESH': None,  # float
    'F2TTL_LIGHT_THRESH': None,  # float
    'F2TTL_CALIBRATION_DATE': None,  # str
    'WATER_CALIBRATION_RANGE': None,  # [min, max]
    'WATER_CALIBRATION_OPEN_TIMES': None,  # [float, float, ...]
    'WATER_CALIBRATION_WEIGHT_PERDROP': None,  # [float, float, ...]
    'WATER_CALIBRATION_DATE': None,  # str
}


def get_board_name():
    iblproject_path = Path(path_helper.get_iblrig_params_folder()) / 'IBL'
    p = Project()
    p.load(str(iblproject_path))
    pars = load_params_file()
    if p.boards[0].name != pars['NAME']:
        pars['NAME'] = p.boards[0].name
        update_params_file(data=pars)
    return pars['NAME']


def write_params_file(data: dict = None, force: bool = False) -> dict:
    """write_params_file wirtes .iblrig_params.json file to default location
    (iblrig/../iblrig_params/.iblrig_params.json)
    If data is None will assume a dict with the default keys and empty values
    write_params_file(data=None, force=True) to reset to empty parameters
    write_params_file(data=some_dict, force=True) to reset to some_dict
    Use update_params_file for upding the values or adding keys

    :param data: Data to write to file, defaults to None i.e. All keys empty
    :type data: dict, optional
    :param force: Force write of data? , defaults to False
    :type force: bool, optional
    :return: params written to file, creates file on disk
    :rtype: dict
    """
    if data is None:
        data = EMPTY_BOARD_PARAMS
        data['NAME'] = get_board_name()
    iblrig_params = Path(path_helper.get_iblrig_params_folder())
    fpath = iblrig_params / '.iblrig_params.json'
    if fpath.exists() and not force:
        log.warning(f"iblrig params file already exists {fpath}. Not writing...")
        return
    with open(fpath, 'w') as f:
        log.info(f"Writing {data} to {fpath}")
        json.dump(data, f, indent=1)
    return data


def load_params_file() -> dict:
    """load_params_file loads the .iblrig_params.json file from default location
     (iblrig/../iblrig_params/.iblrig_params.json), will return None if file not found

    :return: .iblrig_params.json contents
    :rtype: dict or None
    """
    iblrig_params = Path(path_helper.get_iblrig_params_folder())
    fpath = iblrig_params / '.iblrig_params.json'
    if not fpath.exists():
        return None
    with open(fpath, 'r') as f:
        out = json.read(f)
    return out


def update_params_file(data: dict, force: bool = False) -> None:
    """update_params_file updates the values of the params file
    If force will add unknown keys to the file, otherwise it will only add known keys.

    :param data: data to update, keys must be known if force=False
    :type data: dict
    :param force: add unknown keys to file?, defaults to False
    :type force: bool, optional
    :return: Noting, updates file on disk
    :rtype: None
    """
    old = load_params_file()
    if old is None:
        log.info("iblrig params file not found, creating...")
        write_params_file()
        old = load_params_file()

    for k in data:
        if k in old.keys():
            old[k] = data[k]
            log.info(f"Updated {k} with value {data[k]}")
        else:
            if not force:
                log.info(f"Unknown key {k}: skipping key...")
                continue
            elif force:
                log.info(f"Adding new key {k} with value {data[k]} to .iblrig_params.json")
                old[k] = data[k]
    write_params_file(data=old, force=True)
    log.info(f'Changed params file: {data}')

    return old


def update_params(data: dict) -> None:
    update_params_file(data=data)
    try:
        iblrig.alyx.update_board_params(data=data)
    except Exception as e:
        log.warning(f"Could not update board params on Alyx. Saved locally:\n{e}")


def load_params() -> dict:
    out_alyx = iblrig.alyx.load_board_params()
    out = load_params_file()
    if out_alyx is None:
        log.warning(f"Could not load board params from Alyx. Loading from local file...")
        return out
    if out_alyx != out:
        log.warning(f"Local data and Alyx data are not the same. Using local.")
        update_params_file(data=out)
    return out


def write_params(data: dict = None, force: bool = False) -> None:
    iblrig.params.write_params_file(data=data, force=force)
    try:
        iblrig.alyx.write_board_params(data=data, force=force)
    except Exception as e:
        log.warning(f"Could not write board params to Alyx. Written to local file:\n{e}")


def try_migrate_to_params(force=False):
    # See if file exists:
        # Get .bpod_comports file and set the COM values
        # Find latest H2O calib and set WATER values
        # Find latest F2TTL calib and set F2TTL values
        # upload to Alyx board
    # if force do it anyway