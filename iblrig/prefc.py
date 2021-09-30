#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, September 4th 2019, 4:24:59 pm
"""Pre flight checklist
Define task, user, subject and board
Check Alyx connection
    Alyx present:
       Load COM ports
       Load water calibration data and func
       Load frame2TTL thresholds
       Check Bpod, RE, and Frame2TTL
       Set frame2TTL thresholds
       Create folders
       Create session on Alyx
       Open session notes in browser
       Run task
    Alyx absent:

    Load COM ports
end with user input
"""
import datetime
import logging
import struct
from pathlib import Path

import serial
import serial.tools.list_ports
from dateutil.relativedelta import relativedelta
from one.api import ONE
from pybpod_rotaryencoder_module.module_api import RotaryEncoderModule
from pybpod_soundcard_module.module_api import SoundCardModule
from pybpodapi.protocol import Bpod

import iblrig.logging_  # noqa
import iblrig.params as params
from iblrig.frame2TTL import Frame2TTL

log = logging.getLogger("iblrig")
log.setLevel(logging.DEBUG)


def _grep_param_dict(pattern: str = "") -> dict or str:
    """
    Returns subdict of all matches of pattern
    If subdict only has one entry will return just the value
    """
    pardict = params.load_params_file()
    out = {k: pardict[k] for k in pardict if pattern in k}
    if len(out) == 1:
        out = list(out.values())[0]
    return out


def params_comports_ok() -> bool:
    # Load PARAMS file ports
    # If file exists open file if not initialize
    subdict = _grep_param_dict("COM")
    out = True if all(subdict.values()) else False
    if not out:
        log.warning(f"Not all comports are present: \n{subdict}")
    return out


def calibration_dates_ok() -> bool:
    """
    If dates and calibration values are inserted at the same time, checking dates
    should be enough to know if the values are there.
    """
    subdict = _grep_param_dict("DATE")
    out = dict.fromkeys(subdict)
    thresh = {
        "F2TTL_CALIBRATION_DATE": datetime.timedelta(days=7),
        "SCREEN_FREQ_TEST_DATE": relativedelta(months=4),
        "SCREEN_LUX_DATE": relativedelta(months=4),
        "WATER_CALIBRATION_DATE": relativedelta(months=1),
        "BPOD_TTL_TEST_DATE": relativedelta(months=4),
    }
    assert thresh.keys() == subdict.keys()

    today = datetime.datetime.now().date()

    cal_dates_exist = True if all(subdict.values()) else False
    if not cal_dates_exist:
        log.warning(f"Not all calibration dates are present: {subdict}")
    else:
        subdict = {k: datetime.datetime.strptime(v, "%Y-%m-%d").date() for k, v in subdict.items()}
        out = dict.fromkeys(subdict)
        for k in subdict:
            out[k] = subdict[k] + thresh[k] < today
    if not all(out.values()):
        log.warning(f"Outdated calibrations: {[k for k, v in out.items() if not v]}")
    return all(out.values())


def alyx_ok() -> bool:
    out = False
    try:
        ONE()
        out = True
    except BaseException as e:
        log.warning(f"{e}\nCan't connect to Alyx.")
    return out


def local_server_ok() -> bool:
    pars = _grep_param_dict()
    out = Path(pars["DATA_FOLDER_REMOTE"]).exists()
    if not out:
        log.warning("Can't connect to local_server.")
    return out


def rig_data_folder_ok() -> bool:
    pars = _grep_param_dict()
    out = Path(pars["DATA_FOLDER_LOCAL"]).exists()
    if not out:
        log.warning("Can't connect to local_server.")
    return out


def alyx_server_rig_ok() -> bin:
    """
    Try Alyx, try local server, try data folder
    """
    alyx_server_rig = 0b000
    try:
        ONE()
        alyx_server_rig += 0b100
    except BaseException as e:
        log.warning(f"{e} \nCan't connect to Alyx.")

    pars = _grep_param_dict()
    try:
        list(Path(pars["DATA_FOLDER_REMOTE"]).glob("*"))
        alyx_server_rig += 0b010
    except BaseException as e:
        log.warning(f"{e} \nCan't connect to local_server.")

    try:
        list(Path(pars["DATA_FOLDER_LOCAL"]).glob("*"))
        alyx_server_rig += 0b001
    except BaseException as e:
        log.warning(f"{e} \nCan't find rig data folder.")

    return bin(alyx_server_rig)


def rotary_encoder_ok() -> bool:
    # Check RE
    try:
        pars = _grep_param_dict()
        m = RotaryEncoderModule(pars["COM_ROTARY_ENCODER"])
        m.set_zero_position()  # Not necessarily needed
        m.close()
        out = True
    except BaseException as e:
        log.warning(f"{e} \nCan't connect to Rotary Encoder.")
        out = False
    return out


def bpod_ok() -> bool:
    # Check Bpod
    out = False
    try:
        pars = _grep_param_dict()
        bpod = serial.Serial(port=pars["COM_BPOD"], baudrate=115200, timeout=1)
        bpod.write(struct.pack("cB", b":", 0))
        bpod.write(struct.pack("cB", b":", 1))
        bpod.close()
        out = True
    except BaseException as e:
        log.warning(f"{e} \nCan't connect to Bpod.")
    return out


def bpod_modules_ok() -> bool:
    # List bpod modules
    # figure out if RE is in Module 1, Ambient sensore in port 2 and
    # if ephys in board name if SoundCard in port 3
    ephys_rig = "ephys" in _grep_param_dict("NAME")
    if ephys_rig:
        expected_modules = [
            "RotaryEncoder1",
            "AmbientModule1",
            "SoundCard1",
        ]
    else:
        expected_modules = [
            "RotaryEncoder1",
            "AmbientModule1",
        ]
    out = False
    try:
        comport = _grep_param_dict("COM_BPOD")
        bpod = Bpod(serial_port=comport)
        mods = [x.name for x in bpod.modules]
        bpod.close()
        oks = [x in mods for x in expected_modules]
        if all(oks):
            out = True
        else:
            missing = set(expected_modules) - set(mods)
            log.warning(f"Missing modules: {missing}")
    except BaseException as e:
        log.warning(f"{e} \nCan't check modules from Bpod.")

    return out


def f2ttl_ok() -> bool:
    # Check Frame2TTL (by setting the thresholds)
    out = False
    try:
        pars = _grep_param_dict()
        f = Frame2TTL(pars["COM_F2TTL"])
        out = f.ser.isOpen()
        f.close()
    except BaseException as e:
        log.warning(f"{e} \nCan't connect to Frame2TTL.")
    return out


def xonar_ok() -> bool:
    # Check Xonar sound card existence if on ephys rig don't need it
    ephys_rig = "ephys" in _grep_param_dict("NAME")
    if ephys_rig:
        return True
    out = False
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        xonar = [(i, d) for i, d in enumerate(devices) if "XONAR SOUND CARD(64)" in d["name"]]
        if len(xonar) == 1:
            out = True
    except BaseException as e:
        log.warning(f"{e} \nCan't query system sound devices.")

    return out


def harp_sound_card_ok() -> bool:
    # Check HarpSoundCard if on ephys rig
    ephys_rig = "ephys" in _grep_param_dict("NAME")
    harp_sc_name = "Harp Sound Card"
    nscs = len(_list_pc_devices(harp_sc_name))
    if nscs > 1:
        log.warning("Multiple Harp Sound Card devices found")
        return False
    if nscs and ephys_rig:
        scard = SoundCardModule()
        out = scard.connected
        scard.close()
    elif not nscs and ephys_rig:
        out = False
    elif nscs and not ephys_rig:
        log.warning("Harp Sound Card detected: UNUSED, this is a traing rig!")
        out = True
    elif not nscs and not ephys_rig:
        # no sound card no ephys_rig, no problem
        out = True
    return out


def camera_ok() -> bool:
    # Cameras check if on training rig + setup?
    # iblrig.camera_config requires pyspin 37 to be installed
    cam_name = "FLIR USB3 Vision Camera"
    ncams = len(_list_pc_devices(cam_name))
    out = False
    if ncams == 1:
        out = True
    return out


def ultramic_ok() -> bool:
    # Check Mic connection
    mic_name = "UltraMic 200K 16 bit r4"
    nmics = len(_list_pc_devices(mic_name))
    out = False
    if nmics == 1:
        out = True
    return out


# Check Task IO Run fast habituation task with fast delays?

# Ask user info

# Create missing session folders


def _list_pc_devices(grep=""):
    # Tries to list all devices connected to mother board on windows
    # will return list of devices that match grep apttern in field 'Name'
    import win32com.client

    objSWbemServices = win32com.client.Dispatch("WbemScripting.SWbemLocator").ConnectServer(
        ".", r"root\cimv2"
    )

    devices = [i for i in objSWbemServices.ExecQuery("SELECT * FROM Win32_PnPEntity")]
    fields = (
        "Availability",
        "Caption",
        "ClassGuid",
        "ConfigManagerUserConfig",
        "CreationClassName",
        "Description",
        "DeviceID",
        "ErrorCleared",
        "ErrorDescription",
        "InstallDate",
        "LastErrorCode",
        "Manufacturer",
        "Name",
        "PNPDeviceID",
        "PowerManagementCapabilities ",
        "PowerManagementSupported",
        "Service",
        "Status",
        "StatusInfo",
        "SystemCreationClassName",
        "SystemName",
    )

    dev_dicts = {k: {} for k in range(len(devices))}
    for i, d in enumerate(devices):
        dev_dicts[i].update({y: getattr(d, y, None) for y in fields})

    devs = list(dev_dicts.values())
    out = [x for x in devs if x["Name"] and grep.lower() in x["Name"].lower()]
    return out


def rig_ok() -> bool:
    # Stuff to check on all rig types
    {}


def ephys_rig_ok() -> bool:
    # Stuff only present on ephys rig
    {}


def training_rig_ok() -> bool:
    # Stuff only present on training rig
    {}


print(".")
