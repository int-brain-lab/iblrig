import logging
import os
import subprocess
import time
from pathlib import Path


log = logging.getLogger('iblrig')

IBLRIG_FOLDER = r'C:\iblrig'
CWD = os.getcwd()
BONSAI_FOLDER = Path(IBLRIG_FOLDER) / 'Bonsai'

bns = str(BONSAI_FOLDER / 'Bonsai64.exe')
certification_folder = Path(IBLRIG_FOLDER) / 'visual_stim' / 'ephys_certification'
wrkfl = str(certification_folder / 'ephys_certification.bonsai')
SESSION_RAW_DATA_FOLDER = certification_folder

# Flags
noedit = '--no-editor'  # implies start and no-debug?
noboot = '--no-boot'
start = '--start'
# Properties
SA0_DueTime = '-p:SpontaneousActivity0.DueTime=00:15:00'
SA1_DueTime = '-p:SpontaneousActivity1.DueTime=00:15:00'
RFM_FileName = '-p:ReceptiveFieldMappingStim.FileNameRFMapStim=' + str(
    Path(SESSION_RAW_DATA_FOLDER) / '_iblrig_RFMapStim.raw.bin')
RFM_MappingTime = '-p:ReceptiveFieldMappingStim.MappingTime=00:10:00'
CRCS_CheckerboardTime = '-p:ContrastReversingCheckerboardStim.CheckerboardTime=00:03:00'
CSTS_StimFileName = '-p:ContrastSelectivityTaskStim.StimFileName=' + str(
    certification_folder/ 'Extensions' / 'stims.csv')

cmd = [bns, wrkfl, noboot, start, SA0_DueTime, SA1_DueTime,
        RFM_FileName, RFM_MappingTime, CRCS_CheckerboardTime, CSTS_StimFileName]

os.chdir(certification_folder)
s = subprocess.run(cmd, stdout=subprocess.PIPE)  # locking call
os.chdir(CWD)
log.info("You're done, please remove the mouse.\n" * 42)
# Create a transfer_me.flag file
flags.create_transfer_flags(SESSION_FOLDER)
