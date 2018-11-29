# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 27th 2018, 2:10:03 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 27-11-2018 02:10:05.055
"""
Main settings file for water calibration protocol
"""
IBLRIG_FOLDER = "C:\\iblrig"
MAIN_DATA_FOLDER = None  # if None will be C:\\iblrig_data
OAHUS_SCALE_PORT = None  # 'COM2'  # Set to None for manual weight logging

MIN_OPEN_TIME = 10  # (ms)
MAX_OPEN_TIME = 100  # (ms)
STEP = 5  # (ms)

NTRIALS = 100  # number of drops per open time to average across
IPI = 0.5  # (s) Inter Pulse Inster
