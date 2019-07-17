import subprocess
from pathlib import Path

import task_settings
import user_settings  # PyBpod creates this file on run.
from session_params import SessionParamHandler

sph = SessionParamHandler(task_settings, user_settings)

bns = Path(sph.IBLRIG_FOLDER) / 'Bonsai' / 'Bonsai64.exe'
# wrkfl = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / \
#     sph.VISUAL_STIMULUS_TYPE / 'certification.bonsai'
misc_folder = Path(sph.IBLRIG_FOLDER) / 'visual_stim' / 'misc'
stim_01_folder = misc_folder / '01_ReceptiveFieldMappingStim'
stim_02_folder = misc_folder / '02_OrientationDirectionSelectivityStim'
stim_03_folder = misc_folder / '03_ContrastReversingCheckerboardStim'
stim_04_folder = misc_folder / '04_ContrastSelectivityTaskStim'
wrkfl_01 = str(stim_01_folder / 'ReceptiveFieldMappingStim.bonsai')
wrkfl_02 = str(stim_02_folder / 'OrientationDirectionSelectivityStim.bonsai')
wrkfl_03 = str(stim_03_folder / 'ContrastReversingCheckerboardStim.bonsai')
wrkfl_04 = str(stim_04_folder / 'ContrastSelectivityTaskStim.bonsai')

# Flags
noedit = '--no-editor'  # implies start and no-debug?
noboot = '--no-boot'
# Properties
fname = '-p:FileNameRFMapStim=' + str(Path(sph.RAW_DATA_FOLDER / '_iblrig_RFMapStim.raw.bin'))
cmd_01 = [bns, wrkfl_01, noedit, noboot, fname]
cmd_02 = [bns, wrkfl_02, noedit, noboot]
cmd_03 = [bns, wrkfl_03, noedit, noboot]
cmd_04 = [bns, wrkfl_04, noedit, noboot]

s = subprocess.call(cmd_01, stdout=subprocess.PIPE)  # call locks!
s = subprocess.call(cmd_02, stdout=subprocess.PIPE)  # call locks!
s = subprocess.call(cmd_03, stdout=subprocess.PIPE)  # call locks!
s = subprocess.call(cmd_04, stdout=subprocess.PIPE)  # call locks!
