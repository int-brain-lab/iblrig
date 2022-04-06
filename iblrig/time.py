#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: 2022-01-24
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
"""
Library of small time related functions
"""
import numpy as np


def convert_pgts(time):
    """Convert PointGray cameras timestamps to seconds.
    Use convert then uncycle"""
    # offset = time & 0xFFF
    cycle1 = (time >> 12) & 0x1FFF
    cycle2 = (time >> 25) & 0x7F
    seconds = cycle2 + cycle1 / 8000.0
    return seconds


def uncycle_pgts(time):
    """Unwrap the converted seconds of a PointGray camera timestamp series."""
    cycles = np.insert(np.diff(time) < 0, 0, False)
    cycleindex = np.cumsum(cycles)
    return time + cycleindex * 128
