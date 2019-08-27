
# flake8: noqa
SETTINGS_PRIORITY = 0

PYBPOD_SERIAL_PORT       = 'COM3'
PYBPOD_NET_PORT          = 36000

BPOD_BNC_PORTS_ENABLED = [True, True]

BPOD_BEHAVIOR_PORTS_ENABLED = [True, False, False, False]

PYBPOD_API_LOG_LEVEL = None
PYBPOD_API_LOG_FILE  = None

PYBPOD_API_STREAM2STDOUT = False
PYBPOD_API_ACCEPT_STDIN  = True

PYBPOD_PROTOCOL 	= '_iblrig_fake_protocol'
PYBPOD_CREATOR 		= '["_iblrig_fake_user", "f092c2d5-c98a-45a1-be7c-df05f129a93c", "local"]'
PYBPOD_PROJECT 		= 'IBL'
PYBPOD_EXPERIMENT 	= '_iblrig_fake_experiment'
PYBPOD_BOARD 		= '_iblrig_mainenlab_behavior_0'
PYBPOD_SETUP 		= 'fake_setup'
PYBPOD_SESSION 		= '00010131-000001'
PYBPOD_SESSION_PATH = 'C:\\iblrig_params\\IBL\\experiments\\_iblrig_fake\\setups\\fake_setup\\sessions\\00010131-000001'
PYBPOD_SUBJECTS 	= ["['_iblrig_fake_subject', '57b50a6a-29e0-433f-ab82-53b776bfa1be']"]
PYBPOD_SUBJECT_EXTRA = '"{"__UUID4__": "57b50a6a-29e0-433f-ab82-53b776bfa1be", "__DEF-URL__": "http://pybpod.readthedocs.org", "__DEF-TEXT__": "This file contains information about a subject used on PyBpod GUI.", "__SOFTWARE__": "PyBpod GUI API v1.2.1", "name": "_iblrig_fake_mouse", "setup": "None", "uuid4": "57b50a6a-29e0-433f-ab82-53b776bfa1be"}"'
PYBPOD_USER_EXTRA = '{"__UUID4__": "f092c2d5-c98a-45a1-be7c-df05f129a93c", "__DEF-URL__": "http://pybpod.readthedocs.org", "__DEF-TEXT__": "This file contains information about a user used on PyBpod GUI.", "__SOFTWARE__": "PyBpod GUI API v1.2.1"}'


TARGET_BPOD_FIRMWARE_VERSION = '22'

# import logging
# PYBPOD_API_LOG_LEVEL = logging.DEBUG
# PYBPOD_API_LOG_FILE  = 'pybpod-api.log'

PYBPOD_VARSNAMES = []
