import logging

from iblrig import path_helper
from iblrig.base_choice_world import BiasedChoiceWorldSession
from iblrig.hardware import Bpod

log = logging.getLogger("iblrig")


# get hardware settings from 'settings/hardware_settings.yaml file
hardware_settings = path_helper.load_settings_yaml("hardware_settings.yaml")

# check if bpod has had a COM port defined
if hardware_settings["device_bpod"]["COM_BPOD"] is None:
    log.info("No COM port assigned for bpod, edit the 'settings/hardware_settings.yaml' file to add a bpod COM port; skipping "
             "harp validation.")
    exit()

# check if harp is specified as the output device
bpod = Bpod(hardware_settings["device_sound"]["OUTPUT"])
if bpod.sound_card != "harp":
    log.info(f"The sound device specified in 'settings/hardware_settings.yaml' is not 'harp', edit the settings file to change "
             f"this.\nCurrently assigned soundcard: {bpod.sound_card}")
    exit()

# connect to bpod and attempt to produce audio on harp
bpod = Bpod()
cw = BiasedChoiceWorldSession(interactive=False, subject='harp_validator_subject')
cw.start_mixin_bpod()
cw.start_mixin_sound()
# TODO: Flesh out validation
