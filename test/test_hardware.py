import logging
import unittest

from iblrig import path_helper
from iblrig.hardware import Bpod

log = logging.getLogger("iblrig")


class TestHarp(unittest.TestCase):
    def test_harp(self):
        hardware_settings = path_helper.load_settings_yaml("hardware_settings.yaml")  # needed to interface with harp
        if hardware_settings["device_bpod"]["COM_BPOD"] is None:
            log.info("No COM port assigned for bpod, skipping harp test")
        else:
            bpod = Bpod(hardware_settings["device_sound"]["OUTPUT"])
            if bpod.sound_card != "harp":
                log.info("Assigned soundcard ")  # Skip test
        # TODO: Flesh out test


class TestBpod(unittest.TestCase):

    def test_bpod(self):
        bpod = Bpod()
        self.assertIsNotNone(bpod.hardware)
