#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Friday, September 13th 2019, 2:57:40 pm
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
"""
Getting and loading parameters
"""
import json
import logging
import shutil
from pathlib import Path

from pybpodgui_api.models.project import Project

import iblrig
import iblrig.path_helper as ph
from iblrig.graphic import strinput

log = logging.getLogger("iblrig")

# TODO: Add keys for logging all other tests
# Add new keys to this, create optional asker/getter
EMPTY_BOARD_PARAMS = {
    "NAME": None,  # str
    "IBLRIG_VERSION": None,  # str
    "COM_BPOD": None,  # str
    "COM_ROTARY_ENCODER": None,  # str
    "COM_F2TTL": None,  # str
    "F2TTL_HW_VERSION": None,  # float
    "F2TTL_DARK_THRESH": None,  # float
    "F2TTL_LIGHT_THRESH": None,  # float
    "F2TTL_CALIBRATION_DATE": None,  # str
    "SCREEN_FREQ_TARGET": None,  # int (Hz)
    "SCREEN_FREQ_TEST_STATUS": None,  # str
    "SCREEN_FREQ_TEST_DATE": None,  # str
    "SCREEN_LUX_VALUE": None,  # lux (float?)
    "SCREEN_LUX_DATE": None,  # str
    "WATER_CALIBRATION_RANGE": None,  # [min, max]
    "WATER_CALIBRATION_OPEN_TIMES": None,  # [float, float, ...]
    "WATER_CALIBRATION_WEIGHT_PERDROP": None,  # [float, float, ...]
    "WATER_CALIBRATION_DATE": None,  # str
    "BPOD_TTL_TEST_STATUS": None,  # str
    "BPOD_TTL_TEST_DATE": None,  # str
    "DATA_FOLDER_LOCAL": None,  # str
    "DATA_FOLDER_REMOTE": None,  # str
    "DISPLAY_IDX": None,  # int
}

global AUTO_UPDATABLE_PARAMS
AUTO_UPDATABLE_PARAMS = dict.fromkeys(
    ["NAME", "IBLRIG_VERSION", "COM_BPOD", "DATA_FOLDER_LOCAL", "DATA_FOLDER_REMOTE",]
)

DEFAULT_PARAMS = {
    "SCREEN_FREQ_TARGET": 60,
    "DISPLAY_IDX": 1,
}


def ensure_all_keys_present(loaded_params):
    """
    Ensures all keys are present and that empty knowable values are filled
    """
    anything_new = False
    for k in EMPTY_BOARD_PARAMS:
        if k in loaded_params:
            if loaded_params[k] is None and k in AUTO_UPDATABLE_PARAMS:
                loaded_params[k] = update_param_key_values(k)
                anything_new = True
            elif loaded_params[k] is None and k in DEFAULT_PARAMS:
                loaded_params[k] = DEFAULT_PARAMS[k]
                anything_new = True
        elif k not in loaded_params and k in DEFAULT_PARAMS:
            loaded_params[k] = DEFAULT_PARAMS[k]
            anything_new = True
        elif k not in loaded_params and k in AUTO_UPDATABLE_PARAMS:
            loaded_params.update({k: update_param_key_values(k)})
            anything_new = True
        else:
            loaded_params.update({k: EMPTY_BOARD_PARAMS[k]})
            anything_new = True
    if anything_new:
        write_params_file(data=loaded_params, force=True)
    return loaded_params


def create_new_params_dict():
    new_params = EMPTY_BOARD_PARAMS
    new_params = ensure_all_keys_present(new_params)

    return new_params


def update_param_key_values(param_key):
    if param_key == "NAME":
        return get_pybpod_board_name()
    elif param_key == "IBLRIG_VERSION":
        return get_iblrig_version()
    elif param_key == "COM_BPOD":
        return get_pybpod_board_comport()
    elif param_key == "DATA_FOLDER_LOCAL":
        return ph.get_iblrig_data_folder(subjects=False)
    elif param_key == "DATA_FOLDER_REMOTE":
        return ph.get_iblserver_data_folder(subjects=False)
    else:
        return None


def get_iblrig_version():
    return iblrig.__version__


def get_pybpod_board_name():
    iblproject_path = Path(ph.get_iblrig_params_folder()) / "IBL"
    p = Project()
    p.load(str(iblproject_path))
    return p.boards[0].name


def get_board_name():
    params_file = Path(ph.get_iblrig_params_folder()) / ".iblrig_params.json"
    pybpod_board_name = get_pybpod_board_name()
    if not params_file.exists():
        return pybpod_board_name

    pars = load_params_file()
    if pybpod_board_name != pars["NAME"]:
        pars["NAME"] = pybpod_board_name
        update_params_file(data=pars)
    return pars["NAME"]


def get_pybpod_board_comport():
    iblproject_path = Path(ph.get_iblrig_params_folder()) / "IBL"
    p = Project()
    p.load(str(iblproject_path))
    return p.boards[0].serial_port


def get_board_comport():
    params_file = Path(ph.get_iblrig_params_folder()) / ".iblrig_params.json"
    pybpod_board_comport = get_pybpod_board_comport()
    if not params_file.exists():
        return pybpod_board_comport
    pars = load_params_file()

    if pybpod_board_comport != pars["COM_BPOD"]:
        pars["COM_BPOD"] = pybpod_board_comport
        update_params_file(data=pars)
    return pars["COM_BPOD"]


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
    iblrig_params = Path(ph.get_iblrig_params_folder())
    fpath = iblrig_params / ".iblrig_params.json"
    fpath_bckp = iblrig_params / ".iblrig_params_bckp.json"
    if data is None:
        data = create_new_params_dict()
    if fpath.exists() and not force:
        log.warning(f"iblrig params file already exists {fpath}. Not writing...")
        return
    elif fpath.exists() and force:
        shutil.copy(fpath, fpath_bckp)
    if not fpath.exists() or force:
        with open(fpath, "w") as f:
            log.info(f"Writing {data} to {fpath}")
            json.dump(data, f, indent=1)

    return data


def load_params_file(silent=True) -> dict:
    """load_params_file loads the .iblrig_params.json file from default location
     (iblrig/../iblrig_params/.iblrig_params.json), will create default params
     file if file is not found

    :return: .iblrig_params.json contents
    :rtype: dict
    """
    iblrig_params = Path(ph.get_iblrig_params_folder())
    fpath = iblrig_params / ".iblrig_params.json"
    log.debug(f"fpath from load_params_file: {fpath}")
    if fpath.exists():
        with open(fpath, "r") as f:
            out = json.load(f)
        out = ensure_all_keys_present(out)
        if not silent:
            log.info(out)
        return out
    elif not fpath.exists():
        log.warning("Could not load params file does not exist. Creating...")
        out = ask_params_comports(write_params_file())
        return out


def update_params_file(data: dict = None, force: bool = False) -> None:
    """update_params_file updates the values of the params file
    If force will add unknown keys to the file, otherwise it will only add known keys.
    Will update the updatable_params

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

    for k in AUTO_UPDATABLE_PARAMS:
        old[k] = update_param_key_values(k)
    if data is not None:
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
        log.info("Updated params file")

    write_params_file(data=old, force=True)

    return old


def ask_params_comports(data: dict) -> dict:
    patch = {}
    for k in data:
        if "COM" in k and not data[k]:
            newcom = strinput(
                "RIG CONFIG",
                f"Please insert {k.strip('COM_')} COM port (e.g. COM9): ",
                default="COM",
            )
            patch.update({k: newcom})

    if patch:
        data.update(patch)
        update_params_file(data=patch)
        log.debug(f"Updating params file with: {patch}")

    return data


if __name__ == "__main__":
    params = load_params_file()
    print(".")
