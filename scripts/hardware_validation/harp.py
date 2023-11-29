"""
Validation script intended to aid in troubleshooting harp soundcard issues
"""
import logging

from iblrig import path_helper
from iblrig.base_choice_world import BiasedChoiceWorldSession

log = logging.getLogger('iblrig')


# get hardware settings from 'settings/hardware_settings.yaml' file
hardware_settings = path_helper.load_settings_yaml('hardware_settings.yaml')

# check if bpod has had a COM port defined
if hardware_settings['device_bpod']['COM_BPOD'] is None:
    log.info(
        "No COM port assigned for bpod, edit the 'settings/hardware_settings.yaml' file to add a bpod COM port; skipping "
        'harp validation.'
    )
    exit()

# verify harp is set in the 'settings/hardware_settings.yaml' file
if hardware_settings['device_sound']['OUTPUT'] != 'harp':
    log.info(
        f"The sound device specified in 'settings/hardware_settings.yaml' is not 'harp', edit the settings file to change "
        f"this.\nCurrently assigned soundcard: {hardware_settings['device_sound']['OUTPUT']}"
    )
    exit()

# TODO: check device manager for lib-usb32 entries if on Windows system

# connect to bpod and attempt to produce audio on harp
cw = BiasedChoiceWorldSession(interactive=False, subject='harp_validator_subject')
cw.start_mixin_bpod()
log.info('Successfully initialized to bpod.')
cw.start_mixin_sound()
log.info('Successfully initialized to harp audio device')

# TODO: produce audio without creating state machine?
