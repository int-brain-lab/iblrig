#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, May 2nd 2019, 4:28:51 pm
import argparse

try:
    import PySpin
except ImportError:
    raise ImportError(
        "PYSPIN MODULE NOT FOUN IN ENV",
        "Please follow the wiki instructions here:",
        "https://wiki.internationalbrainlab.org/index.php/"
        + "Installing_the_video_acquisition_computer",
    )

SYSTEM = PySpin.System.GetInstance()
CAM_LIST = SYSTEM.GetCameras()
NUM_CAMERAS = CAM_LIST.GetSize()


def enable_trigger_mode(cam_list=None):
    if cam_list is None:
        cam_list = CAM_LIST

    for i, cam in enumerate(cam_list):
        cam.Init()
        nodemap = cam.GetNodeMap()
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode("TriggerMode"))
        node_trigger_mode_on = node_trigger_mode.GetEntryByName("On")
        node_trigger_mode.SetIntValue(node_trigger_mode_on.GetValue())
        print("Trigger mode of camera %d enabled" % i)


def disable_trigger_mode(cam_list=None):
    if cam_list is None:
        cam_list = CAM_LIST

    for i, cam in enumerate(cam_list):
        cam.Init()
        nodemap = cam.GetNodeMap()
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode("TriggerMode"))
        node_trigger_mode_off = node_trigger_mode.GetEntryByName("Off")
        node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())
        print("Trigger mode of camera %d disabled" % i)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize cameras")
    parser.add_argument(
        "-l", required=False, default=False, action="store_true", help="List cameras"
    )
    parser.add_argument(
        "--enable_trig",
        required=False,
        default=False,
        action="store_true",
        help="Enable trigger mode for all cameras",
    )
    parser.add_argument(
        "--disable_trig",
        required=False,
        default=False,
        action="store_true",
        help="Disable trigger mode for all cameras",
    )
    args = parser.parse_args()
    print(args)
    if args.l:
        print(f"Found {CAM_LIST.GetSize()} cameras \n{CAM_LIST}")
    if args.enable_trig:
        enable_trigger_mode()
    elif args.disable_trig:
        disable_trigger_mode()
