#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 27th 2018, 2:10:03 pm
"""
Main settings file for water calibration protocol
"""
IBLRIG_FOLDER = "C:\\iblrig"
IBLRIG_DATA_FOLDER = None  # If None will be ..\\iblrig_data from IBLRIG_FOLDER
OAHUS_SCALE_PORT = None  # 'COM2'  # Set to None for manual weight logging

MIN_OPEN_TIME = 50  # (ms)
MAX_OPEN_TIME = 201  # (ms)
STEP = 50  # (ms)
PASSES = 3  # number of times to repeat the same open_time per run

NTRIALS = 100  # number of drops per open time to average across
IPI = 0.1  # (s) Inter Pulse Interval
