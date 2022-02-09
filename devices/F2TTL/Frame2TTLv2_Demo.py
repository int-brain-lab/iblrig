#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: F2TTL\Frame2TTLv2_Demo.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Tuesday, December 7th 2021, 12:02:24 pm
from Frame2TTLv2 import Frame2TTLv2
import numpy as np

F = Frame2TTLv2('/dev/ttyACM3')
F.lightThreshold = 150  # See note about threshold units in Frame2TTLv2.py
F.darkThreshold = -150
myRawData = F.read_sensor(6)  # Read 20k samples of raw, contiguous sensor data
F.measure_photons(1000)  # Read 1000 samples and report stats

# Also note:

# F.setLightThreshold_Auto() sets the detection threshold for transition from
# dark to light. It should be run while the patch is DARK.
# F.lightThreshold is updated with the new threshold.

# F.setDarkThreshold_Auto() sets the threshold for light --> dark.
# It should be run while the patch is LIGHT.
# F.darkThreshold is updated with the new threshold.

del F
