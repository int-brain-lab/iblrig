import logging
import os
import subprocess
import time
from pathlib import Path

import ibllib.io.flags as flags
# import iblrig.fake_user_settings as user_settings
import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler

log = logging.getLogger('iblrig')

sph = SessionParamHandler(task_settings, user_settings)

CWD = os.getcwd()
BONSAI_FOLDER = Path(sph.IBLRIG_FOLDER) / 'Bonsai'

bns = str(BONSAI_FOLDER / 'Bonsai64.exe')
# wrkfl = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / \
#     sph.VISUAL_STIMULUS_TYPE / 'certification.bonsai'
certification_folder = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / 'ephys_certification'
stim_00_folder = certification_folder / '00_SpacerStim'
stim_01_folder = certification_folder / '01_ReceptiveFieldMappingStim'
stim_02_folder = certification_folder / '02_OrientationDirectionSelectivityStim'
stim_03_folder = certification_folder / '03_ContrastReversingCheckerboardStim'
stim_04_folder = certification_folder / '04_ContrastSelectivityTaskStim'
wrkfl_00 = str(stim_00_folder / 'spacer.bonsai')
wrkfl_01 = str(stim_01_folder / 'ReceptiveFieldMappingStim.bonsai')
wrkfl_02 = str(stim_02_folder / 'OrientationDirectionSelectivityStim.bonsai')
wrkfl_03 = str(stim_03_folder / 'ContrastReversingCheckerboardStim.bonsai')
wrkfl_04 = str(stim_04_folder / 'ContrastSelectivityTaskStim.bonsai')

# Flags
noedit = '--no-editor'  # implies start and no-debug?
noboot = '--no-boot'
# Properties
cmd_01_save_to = '-p:FileNameRFMapStim=' + str(
    Path(sph.SESSION_RAW_DATA_FOLDER) / '_iblrig_RFMapStim.raw.bin')
cmd_01_runtime = '-p:MappingTime=00:10:00'  # '-p:MappingTime=00:00:03'
cmd_03_runtime = '-p:CheckerboardTime=00:03:00'
cmd_04_stims_test = '-p:StimFileName=' + str(stim_04_folder / 'stims.csv')  # 'stims_test.csv')
# Commands
cmd_00 = [bns, wrkfl_00, noedit, noboot]
cmd_01 = [bns, wrkfl_01, noedit, noboot, cmd_01_save_to, cmd_01_runtime]
cmd_02 = [bns, wrkfl_02, noedit, noboot]
cmd_03 = [bns, wrkfl_03, noedit, noboot, cmd_03_runtime]
cmd_04 = [bns, wrkfl_04, noedit, noboot, cmd_04_stims_test]

# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 5. Spontaneous
log.info('Starting 900 seconds of nothingness... [yes, it''s 15 minutes] :)')
time.sleep(900)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 2. Gratings
log.info('Starting Orientation Direction Selectivity Simulus:')
log.info(' '.join(cmd_02))
os.chdir(stim_02_folder)
s = subprocess.run(cmd_02, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 1. Receptive Field mapping
log.info('Starting Receptive Field Mapping Simulus:')
log.info(' '.join(cmd_01))
os.chdir(stim_01_folder)
s = subprocess.run(cmd_01, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 3. Contrast reversal stimuli
log.info('Starting ContrastReversingCheckerboardStim:')
log.info(' '.join(cmd_03))
os.chdir(stim_03_folder)
s = subprocess.run(cmd_03, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 4. Different contrast task stimuli
log.info('Starting ContrastSelectivityTaskStim:')
log.info(' '.join(cmd_04))
os.chdir(stim_04_folder)
s = subprocess.run(cmd_04, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 5. Spontaneous 2
log.info('Starting 900 seconds of nothingness... [yes, it''s 15 minutes] :)')
time.sleep(900)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 2. Gratings 2
log.info('Starting Orientation Direction Selectivity Simulus:')
log.info(' '.join(cmd_02))
os.chdir(stim_02_folder)
s = subprocess.run(cmd_02, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# 0. Spacer
os.chdir(stim_00_folder)
s = subprocess.run(cmd_00, stdout=subprocess.PIPE)  # call locks!
time.sleep(3)
# The end
os.chdir(CWD)
log.info("You're done, please remove the mouse.\n" * 42)
# Create a transfer_me.flag file
flags.create_transfer_flags(sph.SESSION_FOLDER)
