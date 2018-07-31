SETTINGS_PRIORITY = 0

PYBPOD_SERIAL_PORT       = 'COM4'
PYBPOD_NET_PORT          = 36000

BPOD_BNC_PORTS_ENABLED = [True, True]

BPOD_BEHAVIOR_PORTS_ENABLED = [True, True, True, True]

PYBPOD_API_LOG_LEVEL = None
PYBPOD_API_LOG_FILE  = None

PYBPOD_API_STREAM2STDOUT = True
PYBPOD_API_ACCEPT_STDIN  = True

PYBPOD_PROTOCOL     = 'global_timer_example'
PYBPOD_CREATOR      = '["test_user", "b5237473-405d-40e7-b330-42b26ac1b79f", "local"]'
PYBPOD_PROJECT      = 'test'
PYBPOD_EXPERIMENT   = 'Untitled experiment 0'
PYBPOD_BOARD        = 'box'
PYBPOD_SETUP        = 'a'
PYBPOD_SESSION      = '20180629-151450'
PYBPOD_SESSION_PATH = 'C:\\CODE\\BPOD-PROJECTS\\test\\experiments\\Untitled experiment 0\\setups\\a\\sessions\\20180629-151450'
PYBPOD_SUBJECTS     = ["['test_subject', '38a7e29c-a4e0-4a3d-bda4-e95967f6bb4e']"]
PYBPOD_SUBJECT_EXTRA = '"{"url": "http://alyx.champalimaud.pt:8000/subjects/4577", "description": null, "name": "4577", "genotype": null, "__DEF-TEXT__": "This file contains information about a subject used on PyBpod GUI.", "responsible_user": "ines", "uuid4": "e34be842-be51-486c-8c2c-9f43924d1745", "__UUID4__": "e34be842-be51-486c-8c2c-9f43924d1745", "species": "mouse", "sex": "F", "alyx_id": "27705345-f49a-4483-aec8-313fc01d2c1f", "death_date": null, "alive": true, "birth_date": "2017-04-11", "__SOFTWARE__": "PyBpod GUI API v1.0", "nickname": "4577", "strain": "VGlut-2-ChR2-het", "line": null, "__DEF-URL__": "http://pybpod.readthedocs.org", "litter": null}","{"url": "http://alyx.champalimaud.pt:8000/subjects/test_subject", "description": null, "name": "test_subject", "genotype": null, "__DEF-TEXT__": "This file contains information about a subject used on PyBpod GUI.", "responsible_user": "test_user", "uuid4": "38a7e29c-a4e0-4a3d-bda4-e95967f6bb4e", "__UUID4__": "38a7e29c-a4e0-4a3d-bda4-e95967f6bb4e", "species": null, "sex": "U", "alyx_id": "e7935fad-9994-4908-8e6b-ac1221c3c9fd", "death_date": null, "alive": true, "birth_date": null, "__SOFTWARE__": "PyBpod GUI API v1.0", "nickname": "test_subject", "strain": null, "line": null, "__DEF-URL__": "http://pybpod.readthedocs.org", "litter": null}"'
PYBPOD_USER_EXTRA = '{"__SOFTWARE__": "PyBpod GUI API v1.0", "__UUID4__": "b5237473-405d-40e7-b330-42b26ac1b79f", "__DEF-URL__": "http://pybpod.readthedocs.org", "__DEF-TEXT__": "This file contains information about a user used on PyBpod GUI."}'


#import logging
#PYBPOD_API_LOG_LEVEL = logging.DEBUG
#PYBPOD_API_LOG_FILE  = 'pybpod-api.log'

PYBPOD_VARSNAMES = []

if __name__ == '__main__':
    # '["{' --> '[{'    '","' --> ', '    '}"]' --> '}]'
    pass
