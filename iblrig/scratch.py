#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: iblrig/scratch.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Thursday, August 26th 2021, 5:02:19 pm
# Pass input directly to output.
# https://app.assembla.com/spaces/portaudio/git/source/master/test/patest_wire.c
import argparse
import glob
import platform

import serial
import sounddevice as sd


def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "-l",
    "--list-devices",
    action="store_true",
    help="show list of audio devices and exit",
)
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser],
)
parser.add_argument(
    "-i",
    "--input-device",
    type=int_or_str,
    help="input device (numeric ID or substring)",
)
parser.add_argument(
    "-o",
    "--output-device",
    type=int_or_str,
    help="output device (numeric ID or substring)",
)
parser.add_argument("-c", "--channels", type=int, default=2, help="number of channels")
parser.add_argument("--dtype", help="audio data type")
parser.add_argument("--samplerate", type=float, help="sampling rate")
parser.add_argument("--blocksize", type=int, help="block size")
parser.add_argument("--latency", type=float, help="latency in seconds")
args = parser.parse_args(remaining)


def callback(indata, outdata, frames, time, status):
    if status:
        print(status)
    outdata[:] = indata


try:
    with sd.Stream(
        device=(args.input_device, args.output_device),
        samplerate=args.samplerate,
        blocksize=args.blocksize,
        dtype=args.dtype,
        latency=args.latency,
        channels=args.channels,
        callback=callback,
    ):
        print("#" * 80)
        print("press Return to quit")
        print("#" * 80)
        input()
except KeyboardInterrupt:
    parser.exit("")
except Exception as e:
    parser.exit(type(e).__name__ + ": " + str(e))

# %%
# A function that tries to list serial ports on most common platforms
def list_serial_ports():
    system_name = platform.system()
    if system_name == "Windows":
        # Scan for available ports.
        available = []
        for i in range(256):
            comport = f"COM{i}"
            try:
                s = serial.Serial(comport)
                available.append(comport)
                s.close()
            except serial.SerialException:
                pass
        return available
    elif system_name == "Darwin":
        # Mac
        return glob.glob("/dev/tty*") + glob.glob("/dev/cu*")
    else:
        # Assume Linux or something else
        return glob.glob("/dev/ttyS*") + glob.glob("/dev/ttyUSB*")
