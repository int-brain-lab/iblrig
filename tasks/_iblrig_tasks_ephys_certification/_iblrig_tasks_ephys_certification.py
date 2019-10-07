import logging
import os
import subprocess
import time
from pathlib import Path

import ibllib.io.flags as flags
# import iblrig.fake_user_settings as user_settings
import task_settings
import iblrig.fake_user_settings as user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler

log = logging.getLogger('iblrig')

sph = SessionParamHandler(task_settings, user_settings)

CWD = os.getcwd()
BONSAI_FOLDER = Path(sph.IBLRIG_FOLDER) / 'Bonsai'

bns = str(BONSAI_FOLDER / 'Bonsai64.exe')
certification_folder = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / 'ephys_certification'
wrkfl = str(certification_folder / 'ephys_certification.bonsai')

# Flags
noedit = '--no-editor'  # implies start and no-debug?
noboot = '--no-boot'
# Properties
SA0_DueTime = '-p:SpontaneousActivity0.DueTime=00:15:00'
SA1_DueTime = '-p:SpontaneousActivity1.DueTime=00:15:00'
RFM_FileName = '-p:ReceptiveFieldMappingStim.FileNameRFMapStim=' + str(
    Path(sph.SESSION_RAW_DATA_FOLDER) / '_iblrig_RFMapStim.raw.bin')
RFM_MappingTime = '-p:ReceptiveFieldMappingStim.MappingTime=00:10:00'
CRCS_CheckerboardTime = '-p:ContrastReversingCheckerboardStim.CheckerboardTime=00:03:00'
CSTS_StimFileName = '-p:ContrastSelectivityTaskStim.StimFileName=' + str(
    certification_folder/ 'Extensions' / 'stims.csv')

cmd = [bns, wrkfl, noedit, noboot, SA0_DueTime, SA1_DueTime,
        RFM_FileName, RFM_MappingTime, CRCS_CheckerboardTime, CSTS_StimFileName]

os.chdir(certification_folder)
s = subprocess.run(cmd, stdout=subprocess.PIPE)  # locking call
os.chdir(CWD)
log.info("You're done, please remove the mouse.\n" * 42)
# Create a transfer_me.flag file
flags.create_transfer_flags(sph.SESSION_FOLDER)
