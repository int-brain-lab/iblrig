#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, June 6th 2019, 11:42:40 am
import logging
import math

import numpy as np
from pythonosc import udp_client

import iblrig.frame2TTL as frame2TTL
import iblrig.iotasks as iotasks
import iblrig.user_input as user_input
from iblrig.misc import make_square_dvamat, checkerboard
from iblrig.path_helper import SessionPathCreator

log = logging.getLogger('iblrig')


class SessionParamHandler(object):
    """Session object imports user_settings and task_settings
    will and calculates other secondary session parameters,
    runs Bonsai and saves all params in a settings file.json"""

    def __init__(self, task_settings, user_settings):
        # =====================================================================
        # IMPORT task_settings, user_settings, and SessionPathCreator params
        # =====================================================================
        ts = {i: task_settings.__dict__[i]
              for i in [x for x in dir(task_settings) if '__' not in x]}
        self.__dict__.update(ts)
        us = {i: user_settings.__dict__[i]
              for i in [x for x in dir(user_settings) if '__' not in x]}
        self.__dict__.update(us)
        self = iotasks.deserialize_pybpod_user_settings(self)
        spc = SessionPathCreator(self.IBLRIG_FOLDER, self.IBLRIG_DATA_FOLDER,
                                 self.PYBPOD_SUBJECTS[0],
                                 protocol=self.PYBPOD_PROTOCOL,
                                 board=self.PYBPOD_BOARD, make=True)
        self.__dict__.update(spc.__dict__)

        # =====================================================================
        # OSC CLIENT
        # =====================================================================
        self.OSC_CLIENT_PORT = 7110
        self.OSC_CLIENT_IP = '127.0.0.1'
        self.OSC_CLIENT = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP,
                                                     self.OSC_CLIENT_PORT)
        # =====================================================================
        # frame2TTL
        # =====================================================================
        self.F2TTL_GET_AND_SET_THRESHOLDS = frame2TTL.get_and_set_thresholds(self)
        # =====================================================================
        # PROBES + WEIGHT
        # =====================================================================
        self.FORM_DATA = user_input.session_form(mouse_name=self.SUBJECT_NAME)
        self = user_input.parse_form_data(self)
        # =====================================================================
        # VISUAL STIM
        # =====================================================================
        self.VISUAL_STIMULUS_FILE = None
        self.SCREEN_DIMENSIONS = {'width': 20, 'height': 15}  # cm
        self.SCREEN_EXTRINSICS = {'rotation': (0, 0, 0), 'translation': (0, 0, -8)}
        self.SCREEN_VISUAL_SPAN_X = np.rad2deg(
            math.atan(self.SCREEN_DIMENSIONS['width'] / 2 / abs(
                self.SCREEN_EXTRINSICS['translation'][2]))) * 2
        self.SCREEN_VISUAL_SPAN_Y = np.rad2deg(
            math.atan(self.SCREEN_DIMENSIONS['height'] / 2 / abs(
                self.SCREEN_EXTRINSICS['translation'][2]))) * 2
        self.VISUAL_STIMULI = {
            0: 'SPACER',
            1: 'receptive_field_mapping',
            2: 'orientation-direction_selectivity',
            3: 'contrast_reversal',
            4: 'task_stimuli',
            5: 'spontaneous_activity',
        }
        self.STIM_ORDER = [0, 5, 0, 2, 0, 1, 0, 3, 0, 4, 0, 5, 0, 2, 0]

        self.VISUAL_STIM_0 = {
            'ttl_num': 16,
            'ttl_frame_nums': [1, 2, 4, 8, 16, 32, 64, 128, 192, 224, 240, 248, 252, 254, 255, 256]
        }
        self.VISUAL_STIM_1 = {
            'ttl_num': None,
            'stim_shape': 'square',
            'stim_npatches': 15 * 15,
            'patch_dva': 8,
            'dva_mat': make_square_dvamat(size=15, dva=8),
            'stim_data_file_name': '_iblrig_RFMapStim.raw.bin',
            'stim_file_shape': [15, 15, 'nframes'],
        }
        self.VISUAL_STIM_2 = {
            'ttl_num': 320,
            'stim_directions_rad': {
                1: 3 * np.pi / 2,
                2: 5 * np.pi / 4,
                3: 1 * np.pi / 1,
                4: 3 * np.pi / 4,
                5: 1 * np.pi / 2,
                6: 1 * np.pi / 4,
                7: 0 * np.pi / 2,
                8: 7 * np.pi / 4,
            },
            'stim_sequence': [1, 2, 3, 4, 5, 6, 7, 8] * 20,
            'stim_tf': 2,  # Hz
            'stim_cpd': 0.05,  # spatial freq, cycles per degree
            'stim_on_time': 2,  # seconds
            'stim_off_time': 1,  # seconds
        }
        self.VISUAL_STIM_3 = {
            'ttl_num': 180,
            'stim_shape': 'square',
            'stim_npatches': 15 * 15,
            'patch_dva': 25,
            'dva_mat': make_square_dvamat(size=15, dva=25),
            'stim_patch_contrasts': {
                1: checkerboard((15, 15)) * 255,
                2: np.abs(checkerboard((15, 15)) - 1) * 255
            },
            'stim_sequence': [1, 2] * 90,
            'stim_on_time': 1,  # seconds
            'stim_off_time': 0,  # seconds
        }
        self.VISUAL_STIM_4 = {
            'ttl_num': 400,
            'stim_spatial_freq': 0.1,  # cyc/º
            'sigma': 7**2,  # dva
            'elevation': 0,
            'orientation': 0,
            'phase': 0,
            'stim_on_time': 2,  # seconds
            'stim_off_time': 1,  # seconds
            'stim_azimuth_set': [-35, 35],
            'stim_contrast_set': [1.0, 0.5, 0.25, 0.125, 0.0625],
            'stim_file':
                'iblrig/visual_stim/ephys_certification/04_ContrastSelectivityTaskStim/stims.csv',
            'stim_file_columns': ('azimuth', 'contrast')
        }
        # =====================================================================
        # SAVE SETTINGS FILE AND TASK CODE
        # =====================================================================
        iotasks.copy_task_code(self)
        iotasks.save_task_code(self)
        iotasks.save_session_settings(self)

    # =========================================================================
    # METHODS
    # =========================================================================

    # =========================================================================
    # JSON ENCODER PATCHES
    # =========================================================================
    def reprJSON(self):
        d = self.__dict__.copy()
        d['OSC_CLIENT'] = str(d['OSC_CLIENT'])
        d['VISUAL_STIM_1']['dva_mat'] = d['VISUAL_STIM_1']['dva_mat'].tolist()
        d['VISUAL_STIM_3']['dva_mat'] = d['VISUAL_STIM_3']['dva_mat'].tolist()
        d['VISUAL_STIM_3']['stim_patch_contrasts'][1] = d[
            'VISUAL_STIM_3']['stim_patch_contrasts'][1].tolist()
        d['VISUAL_STIM_3']['stim_patch_contrasts'][2] = d[
            'VISUAL_STIM_3']['stim_patch_contrasts'][2].tolist()
        return d


if __name__ == '__main__':
    import task_settings
    import iblrig.fake_user_settings as user_settings
    from pathlib import Path
    iblrig_folder = Path(__file__).parent.parent.parent
    task_settings.IBLRIG_FOLDER = iblrig_folder
    user_settings.PYBPOD_PROTOCOL = '_iblrig_tasks_ephys_certification'
    sph = SessionParamHandler(task_settings, user_settings)
    print("Done!")
