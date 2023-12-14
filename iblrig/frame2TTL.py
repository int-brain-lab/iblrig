#!/usr/bin/env python
# @File: iblrig/frame2TTL.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Friday, November 5th 2021, 12:47:34 pm
# @Creation_Date: 2018-06-08 11:04:05
import struct
import time

import numpy as np
import serial

from iblutil.util import setup_logger

log = setup_logger('iblrig')


def frame2ttl_factory(serial_port: str, version: int = 2):
    f2ttl = Frame2TTLv2(serial_port)
    if f2ttl.hw_version != 2:
        f2ttl.close()
        f2ttl = Frame2TTLv1(serial_port)
    return f2ttl


class Frame2TTL:
    """Determine whether to use v1 or v2 by trying to connect to v2 and find the hw_version

    Args:
        serial_port (str): Serial port where the device is connected

    Returns:
        object: Instance of the v1/v2 class
    """

    hw_version = None
    streaming = False
    measured_black = None
    measured_white = None
    recomend_dark = None
    recomend_light = None

    def __init__(self, serial_port: str, version: int = 2):
        assert serial_port is not None
        self.serial_port = serial_port
        self.serial = None
        self.connect()

    @property
    def connected(self):
        return self.serial.isOpen() if self.serial else False

    def connect(self):
        """Create connection to serial_port"""
        if not self.connected:
            self.serial = serial.Serial(port=self.serial_port, baudrate=115200, timeout=3.0, write_timeout=1.0)

    def close(self) -> None:
        """Close connection to serial port"""
        if self.connected:
            self.serial.close()


class Frame2TTLv1(Frame2TTL):
    def __init__(self, serial_port: str):
        super().__init__(serial_port)
        self.light_threshold = 40
        self.dark_threshold = 80
        try:
            assert self.handshake() == 218, 'Frams2TTL handshake failed, abort.'
            return
        except AssertionError as e:
            log.error(
                f"Couldn't connect to F2TTLv1: {str(e)}\nDisconnecting and then "
                f'reconnecting the Frame2TTL cable may resolve this issue.'
            )
            raise e

    def handshake(self):
        # Handshake
        # ser.write(struct.pack("c", b"C"))
        self.serial.write(b'C')
        # 1 byte response expected (unsigned)
        handshakeByte = int.from_bytes(self.serial.read(1), byteorder='little', signed=False)
        if handshakeByte != 218:
            raise serial.SerialException('Handshake with F2TTL device failed')
        return handshakeByte

    def start_stream(self) -> None:
        """Enable streaming to USB (stream rate 100Hz)
        response = int.from_bytes(self.ser.read(4), byteorder='little')"""
        self.serial.write(struct.pack('cB', b'S', 1))
        self.streaming = True

    def stop_stream(self) -> None:
        """Disable streaming to USB"""
        self.serial.write(struct.pack('cB', b'S', 0))
        self.streaming = False

    def read_value(self) -> int:
        """Read one value from sensor (current)"""
        self.serial.write(b'V')
        response = self.serial.read(4)
        # print(np.frombuffer(response, dtype=np.uint32))
        response = int.from_bytes(response, byteorder='little')
        return response

    def measure_photons(self, num_samples: int = 250) -> dict:
        """Measure <num_samples> values from the sensor and return basic stats.
        Mean, Std, SEM, Nsamples
        """
        import time

        sample_sum = []
        for _i in range(num_samples):
            sample_sum.append(self.read_value())
            time.sleep(0.001)

        out = {
            'mean_value': float(np.array(sample_sum).mean()),
            'max_value': float(np.array(sample_sum).max()),
            'min_value': float(np.array(sample_sum).min()),
            'std_value': float(np.array(sample_sum).std()),
            'sem_value': float(np.array(sample_sum).std() / np.sqrt(num_samples)),
            'nsamples': float(num_samples),
        }
        return out

    def set_thresholds(self, dark=None, light=None) -> None:
        """Set light, dark, or both thresholds for the device"""
        if dark is None:
            dark = self.dark_threshold
        if light is None:
            light = self.light_threshold

        self.serial.write(b'C')
        response = self.serial.read(1)
        if response[0] != 218:
            raise (ConnectionError)

        # Device wants light threshold before dark
        self.serial.write(struct.pack('<BHH', ord('T'), int(light), int(dark)))
        if light != self.light_threshold:
            log.info(f'Light threshold set to {light}')
        if dark != self.dark_threshold:
            log.info(f'Dark threshold set to {dark}')
        if light == 40 and dark == 80:
            log.info(f'Reset to default values: light={light} - dark={dark}')
        self.dark_threshold = dark
        self.light_threshold = light

    def calc_recomend_thresholds(self):
        if (self.measured_black is None) or (self.measured_white is None):
            log.error('No mesures exist')
            return -1
        self.recomend_light = self.measured_white.get('max_value')
        if self.measured_black['min_value'] - self.recomend_light > 40:
            self.recomend_dark = self.recomend_light + 40
        else:
            self.recomend_dark = round(self.recomend_light + ((self.measured_black['min_value'] - self.recomend_light) / 3))
        if self.recomend_dark - self.recomend_light < 5:
            (log.error('Cannot recommend thresholds:'),)
            log.error('Black and White measurements may be too close for accurate frame detection')
            log.error(f'Light = {self.recomend_light}, Dark = {self.recomend_dark}')
            return -1
        else:
            log.info('Recommended thresholds:')
            log.info(f'Light ={self.recomend_light}, Dark = {self.recomend_dark}.')
            print('Done')
            return self.recomend_dark, self.recomend_light

    def set_recommendations(self):
        log.info('Sending thresholds to device...')
        self.set_thresholds(dark=self.recomend_dark, light=self.recomend_light)

    def suggest_thresholds(self) -> None:
        input('Set pixels under Frame2TTL to white (rgb 255,255,255) and press enter >')
        print(' ')
        print('Measuring white...')
        white_data = self.measure_photons(10000)

        input('Set pixels under Frame2TTL to black (rgb 0,0,0) and press enter >')
        print(' ')
        print('Measuring black...')
        dark_data = self.measure_photons(10000)
        print(' ')
        light_max = white_data.get('max_value')
        dark_min = dark_data.get('min_value')
        print(f'Max sensor reading for white (lower is brighter) = {light_max}.')
        print(f'Min sensor reading for black = {dark_min}.')
        recomend_light = light_max
        if dark_min - recomend_light > 40:
            recomend_dark = recomend_light + 40
        else:
            recomend_dark = round(recomend_light + ((dark_min - recomend_light) / 3))
        if recomend_dark - recomend_light < 5:
            print(
                'Error: Cannot recommend thresholds:',
                'light and dark measurements may be too close for accurate frame detection',
            )
        else:
            log.info(f'Recommended thresholds: Light = {recomend_light}, Dark = {recomend_dark}.')
            log.info('Sending thresholds to device...')
            self.recomend_dark = recomend_dark
            self.recomend_light = recomend_light
            self.set_thresholds(light=recomend_light, dark=recomend_dark)
            print('Done')


class Frame2TTLv2(Frame2TTL):
    def __init__(self, serial_port: str):
        super().__init__(serial_port)
        self.dark_threshold = -150
        self.light_threshold = 100

    def connect(self):
        """Create connection to serial_port
        Perform a handshake and confirm it's a version 2 device
        """
        super().connect()
        try:
            self.serial.write(b'C')
            # 1 byte response expected (unsigned)
            handshakeByte = int.from_bytes(self.serial.read(1), byteorder='little', signed=False)
            if handshakeByte != 218:
                self.close()
                raise ValueError('Handshake with F2TTL device failed')
            # HW version
            # ser.write(struct.pack("c", b"#"))
            self.serial.write(b'#')
            # 1 byte response expected (unsigned)
            self.hw_version = int.from_bytes(self.serial.read(1), byteorder='little', signed=False)
            if self.hw_version != 2:
                self.close()
        except serial.SerialException as e:
            self.close()
            raise serial.SerialException(
                'Could not connect to the Frame2ttl device, please power cycle the device by '
                'disconnecting / reconnecting the USB cable and try again. '
                'If after a power cycle the error remains, make sure the correct COM port is '
                'defined in the ./settings/hardware_settings.yaml file'
            ) from e

    def start_stream(self) -> None:
        """Enable streaming to USB (stream rate 100Hz? sensor samples at 20kHz)
        minicom --device /dev/ttyACM0 --baud 115200
        response = int.from_bytes(self.ser.read(4), byteorder='little')"""
        # char "S" plus 1 byte [0, 1] (uint8)
        # self.ser.write(struct.pack("cB", b"S", 1))
        self.serial.write(b'S' + int.to_bytes(1, 1, byteorder='little', signed=False))
        self.streaming = True

    def stop_stream(self) -> None:
        """Disable streaming to USB"""
        # char "S" plus 1 byte [0, 1] (uint8)
        # self.ser.write(struct.pack("cB", b"S", 0))
        self.serial.write(b'S' + int.to_bytes(1, 0, byteorder='little', signed=False))
        self.streaming = False

    def read_sensor(self, nsamples: int = 1) -> int:
        """Reads N contiguous samples from the sensor (raw data)
        Command: 5 bytes | [b"V" (uint8), nSamples (uint32)]
        Response: 2 bytes * nsamples | [sensorValue (uint16) * nsamples]
        """
        # self.ser.write(struct.pack("cB", b"V", nsamples))
        self.serial.write(b'V' + int.to_bytes(nsamples, 4, byteorder='little', signed=False))
        dt = np.dtype(np.uint16)
        dt = dt.newbyteorder('<')
        values = np.frombuffer(self.serial.read(nsamples * 2), dtype=dt)
        if len(values) != nsamples:
            log.error(f'Failed to read {nsamples} samples from device')
        return values

    def read_value(self) -> int:
        """Read one value from sensor (current)"""
        return self.read_sensor()

    def measure_black(self, mode='auto'):
        """Measure black levels and calculate light threshold.
        Command: 1 bytes | b"L" (uint8)
        Response: 2 bytes | value (int16)
        """
        log.info('Measuring BLACK variability to find LIGHT threshold...')
        if mode == 'auto':
            # Run the firmware routine to find the light threshold
            self.serial.write(b'L')
            time.sleep(3)
            threshold = int.from_bytes(self.serial.read(2), byteorder='little', signed=True)
            self.auto_light = threshold
            log.info(f'Auto LIGHT threshold value: {threshold}')
        elif mode == 'manual':
            arr = self.read_sensor(20000)
            if len(arr) != 20000:
                log.warning('Manual LIGHT threshold value could not be determined.')
                threshold = None
            else:
                threshold = self._calc_threshold(arr, light=True)
            self.manual_light = threshold
            log.info(f'Manual LIGHT threshold value: {threshold}')
            return arr, threshold

    def measure_white(self, mode='auto'):
        """Measure white levels and calculate dark threshold.
        Command: 1 bytes | b"D" (uint8)
        Response: 2 bytes | value (int16)
        """
        log.info('Measuring WHITE variability to find DARK threshold...')
        if mode == 'auto':
            # Run the firmware routine to find the dark threshold
            self.serial.write(b'D')
            time.sleep(3)
            threshold = int.from_bytes(self.serial.read(2), byteorder='little', signed=True)
            self.auto_dark = threshold
            log.info(f'Auto DARK threshold value: {threshold}')
        elif mode == 'manual':
            arr = self.read_sensor(20000)
            if len(arr) != 20000:
                log.warning('Manual DARK threshold value could not be determined.')
                threshold = None
            else:
                threshold = self._calc_threshold(arr, dark=True)
            self.manual_dark = threshold
            log.info(f'Manual DARK threshold value: {threshold}')
            return arr, threshold

    def _calc_threshold(self, arr, dark=False, light=False):
        """Calc the light/dark threshold using hardware values
        Of 20000 samples calculate the means of the changes in value of each
        sliding window of 20 samples from the beginning to the end of the array.
        - If the array is from a black sync square this will set the light threshold
        by multiplying the max mean diff value by 1.5
        - If the array is from a white sync square this will set the dark threshold
        by multiplying the min mean diff value by 2
        """
        mean_diffs = []
        for i, _ in enumerate(arr):
            if i + 20 <= len(arr):
                mean_diffs.append(np.diff(arr[i : i + 20]).mean())
        if dark:
            return np.min(mean_diffs) * 2
        if light:
            return np.max(mean_diffs) * 1.5

    def calc_recomend_thresholds(self):
        """Calculate / check (name maintained for compatibility reasons)
        recomended light and dark thresholds for the sensor
        from the auto and manual measurments and calculations.
        """
        manual_calib_run = self.manual_dark is not None and self.manual_light is not None
        auto_calib_run = self.auto_dark is not None and self.auto_light is not None
        if not auto_calib_run:
            log.info('No measurments detected for automatic calibration.')
        if not manual_calib_run:
            log.info('No measurments detected for manual calibration.')
        if not auto_calib_run and not manual_calib_run:
            log.error('Please run .measure_white and .measure_black to recalculate thresholds.')
            return -1
        # Check if manual and auto recomendations are similar
        if auto_calib_run and manual_calib_run:
            assert np.allclose(
                self.auto_dark, self.manual_dark, atol=75
            ), 'Values of manual and auto calibration are too different.'
            assert np.allclose(
                self.auto_light, self.manual_light, atol=75
            ), 'Values of manual and auto calibration are too different.'

        # Either use the auto calib after verifying they are close to the manual ones
        # or use the manual values if they are the only ones. Default to the auto values
        self.recomend_dark = self.auto_dark or self.manual_dark
        self.recomend_light = self.auto_light or self.manual_light

        if self.auto_dark > self.auto_light:
            (log.error('Something looks wrong with the thresholds!'),)
            log.error('Dark threshold must be lower than light threshold')
            log.error(f'Dark = {self.auto_dark}, Light = {self.auto_light}')
            return -1
        else:
            log.info('Recommended thresholds:')
            log.info(f'Light ={self.recomend_light}, Dark = {self.recomend_dark}.')
            log.warning('Recommended thresholds not set yet. Please call set_recommendations()')
            return self.recomend_dark, self.recomend_light

    def set_thresholds(self, light, dark):
        """Set both thresholds
        Command: 5 bytes | [b"T" (uint8), (light_threshold (int16), dark_threshold (int16))]
        Response: None
        """
        log.info(f'Setting dark threshold to {dark}')
        log.info(f'Setting light threshold to {light}')
        self.serial.write(
            b'T'
            + int.to_bytes(int(light), 2, byteorder='little', signed=True)
            + int.to_bytes(int(dark), 2, byteorder='little', signed=True)
        )
        self.light_threshold = light
        self.dark_threshold = dark

    def set_recommendations(self):
        log.info('Sending thresholds to device...')
        self.set_thresholds(dark=self.recomend_dark, light=self.recomend_light)

    def __repr__(self) -> str:
        return f"""
            Bpod Frame2TTL device version 2.0
            Serial port:        {self.serial_port}
            Connected:          {self.connected}
            Streaming:          {self.streaming}
            Dark Threshold:     {self.dark_threshold}
            Light Threshold:    {self.light_threshold}"""

    def reset_thresholds(self):
        self.dark_threshold = -150
        self.light_threshold = 150
