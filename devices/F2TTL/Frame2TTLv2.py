#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: F2TTL\Frame2TTLv2.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Tuesday, December 7th 2021, 12:01:50 pm
from ArCOM_F2TTL import ArCOM
import numpy as np
import time


class Frame2TTLv2(object):
    def __init__(self, PortName):
        self.Port = ArCOM(PortName, 115200)
        self.Port.write(ord("C"), "uint8")
        handshakeByte = self.Port.read(1, "uint8")
        if handshakeByte != 218:
            raise F2TTLError("Error: Frame2TTL not detected on port " + PortName + ".")
        self.Port.write(ord("#"), "uint8")
        hardwareVersion = self.Port.read(1, "uint8")
        if hardwareVersion != 2:
            raise F2TTLError("Error: Frame2TTLv2 requires hardware version 2.")
        self._lightThreshold = 150
        # This is not a threshold of raw sensor data.
        self._darkThreshold = -150
        # It is a 20-sample sliding window avg of
        # sample-wise differences in the raw signal.

    @property
    def lightThreshold(self):
        return self._lightThreshold

    @lightThreshold.setter
    def lightThreshold(self, value):
        self.Port.write(ord("T"), "uint8", (value, self.darkThreshold), "int16")
        self._lightThreshold = value

    @property
    def darkThreshold(self):
        return self._darkThreshold

    @darkThreshold.setter
    def darkThreshold(self, value):
        self.Port.write(ord("T"), "uint8", (self.lightThreshold, value), "int16")
        self._darkThreshold = value

    def setLightThreshold_Auto(self):  # Run with the sync patch set to black
        self.Port.write(ord("L"), "uint8")
        time.sleep(3)
        newThreshold = self.Port.read(1, "int16")
        self.lightThreshold = newThreshold[0]

    def setDarkThreshold_Auto(self):  # Run with the sync patch set to white
        self.Port.write(ord("D"), "uint8")
        time.sleep(3)
        newThreshold = self.Port.read(1, "int16")
        self.darkThreshold = newThreshold[0]

    def read_sensor(self, nSamples):  # Return contiguous samples (raw sensor data)
        self.Port.write(ord("V"), "uint8", nSamples, "uint32")
        value = self.Port.read(nSamples, "uint16")
        return value

    def measure_photons(self, num_samples: int = 250) -> dict:
        """Measure <num_samples> values from the sensor and return basic stats.
        Mean, Std, SEM, Nsamples
        """
        sensorData = self.read_sensor(num_samples)
        out = {
            "mean_value": float(sensorData.mean()),
            "max_value": float(sensorData.max()),
            "min_value": float(sensorData.min()),
            "std_value": float(sensorData.std()),
            "sem_value": float(sensorData.std() / np.sqrt(num_samples)),
            "nsamples": float(num_samples),
        }
        return out

    def __repr__(self):
        """Self description when the object is entered into the IPython console
        with no properties or methods specified
        """
        return (
            "\nBpodHiFi with user properties:" + "\n\n"
            "Port: ArCOMObject(" + self.Port.serialObject.port + ")" + "\n"
            "lightThreshold: " + str(self.lightThreshold) + "\n"
            "darkThreshold: " + str(self.darkThreshold) + "\n"
        )

    def __del__(self):
        self.Port.close()


class F2TTLError(Exception):
    pass


if __name__ == "__main__":
    # Example usage:
    # port = 'COM4'
    # port = '/dev/ttyACM0'
    port = "/dev/serial/by-id/usb-Teensyduino_USB_Serial_10295450-if00"
    f = Frame2TTLv2(port)
    print(f)

    # Bus 001 Device 012: ID 16c0:0483 Van Ooijen Technische Informatica Teensyduino Serial
