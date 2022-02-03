import logging
import struct
import time

import numpy as np
import serial

import iblrig.alyx
import iblrig.params

log = logging.getLogger("iblrig")


class Frame2TTL(object):
    def __init__(self, serial_port) -> None:
        pass

class Frame2TTLv1(Frame2TTL):
    def __init__(self, serial_port):
        self.serial_port = serial_port
        self.connected = False
        self.ser = self.connect(serial_port)
        self.light_threshold = 40
        self.dark_threshold = 80
        self.streaming = False
        self.measured_black = None
        self.measured_white = None
        self.recomend_dark = None
        self.recomend_light = None

    def connect(self, serial_port) -> serial.Serial:
        """Create connection to serial_port"""
        ser = serial.Serial(port=serial_port, baudrate=115200, timeout=1.0, write_timeout=1.0)
        self.connected = ser.isOpen()
        return ser

    def close(self) -> None:
        """Close connection to serial port"""
        self.ser.close()
        self.connected = self.ser.isOpen()

    def start_stream(self) -> None:
        """Enable streaming to USB (stream rate 100Hz)
        response = int.from_bytes(self.ser.read(4), byteorder='little')"""
        self.ser.write(struct.pack("cB", b"S", 1))
        self.streaming = True

    def stop_stream(self) -> None:
        """Disable streaming to USB"""
        self.ser.write(struct.pack("cB", b"S", 0))
        self.streaming = False

    def read_value(self) -> int:
        """Read one value from sensor (current)"""
        self.ser.write(b"V")
        response = self.ser.read(4)
        # print(np.frombuffer(response, dtype=np.uint32))
        response = int.from_bytes(response, byteorder="little")
        return response

    def measure_photons(self, num_samples: int = 250) -> dict:
        """Measure <num_samples> values from the sensor and return basic stats.
        Mean, Std, SEM, Nsamples
        """
        import time

        sample_sum = []
        for i in range(num_samples):
            sample_sum.append(self.read_value())
            time.sleep(0.001)

        out = {
            "mean_value": float(np.array(sample_sum).mean()),
            "max_value": float(np.array(sample_sum).max()),
            "min_value": float(np.array(sample_sum).min()),
            "std_value": float(np.array(sample_sum).std()),
            "sem_value": float(np.array(sample_sum).std() / np.sqrt(num_samples)),
            "nsamples": float(num_samples),
        }
        return out

    def set_thresholds(self, dark=None, light=None) -> None:
        """Set light, dark, or both thresholds for the device"""
        if dark is None:
            dark = self.dark_threshold
        if light is None:
            light = self.light_threshold

        self.ser.write(b"C")
        response = self.ser.read(1)
        if response[0] != 218:
            raise (ConnectionError)

        # Device wants light threshold before dark
        self.ser.write(struct.pack("<BHH", ord("T"), int(light), int(dark)))
        if light != self.light_threshold:
            log.info(f"Light threshold set to {light}")
        if dark != self.dark_threshold:
            log.info(f"Dark threshold set to {dark}")
        if light == 40 and dark == 80:
            log.info(f"Resetted to default values: light={light} - dark={dark}")
        self.dark_threshold = dark
        self.light_threshold = light

    def measure_white(self):
        log.info("Measuring white...")
        self.measured_white = self.measure_photons(1000)
        return self.measured_white

    def measure_black(self):
        log.info("Measuring black...")
        self.measured_black = self.measure_photons(1000)
        return self.measured_black

    def calc_recomend_thresholds(self):
        if (self.measured_black is None) or (self.measured_white is None):
            log.error("No mesures exist")
            return -1
        self.recomend_light = self.measured_white.get("max_value")
        if self.measured_black["min_value"] - self.recomend_light > 40:
            self.recomend_dark = self.recomend_light + 40
        else:
            self.recomend_dark = round(
                self.recomend_light
                + ((self.measured_black["min_value"] - self.recomend_light) / 3)
            )
        if self.recomend_dark - self.recomend_light < 5:
            log.error("Cannot recommend thresholds:"),
            log.error("Black and White measurements may be too close for accurate frame detection")
            log.error(f"Light = {self.recomend_light}, Dark = {self.recomend_dark}")
            return -1
        else:
            log.info("Recommended thresholds:")
            log.info(f"Light ={self.recomend_light}, Dark = {self.recomend_dark}.")
            print("Done")
            return self.recomend_dark, self.recomend_light

    def set_recommendations(self):
        log.info("Sending thresholds to device...")
        self.set_thresholds(dark=self.recomend_dark, light=self.recomend_light)

    def suggest_thresholds(self) -> None:
        input("Set pixels under Frame2TTL to white (rgb 255,255,255) and press enter >")
        print(" ")
        print("Measuring white...")
        white_data = self.measure_photons(10000)

        input("Set pixels under Frame2TTL to black (rgb 0,0,0) and press enter >")
        print(" ")
        print("Measuring black...")
        dark_data = self.measure_photons(10000)
        print(" ")
        light_max = white_data.get("max_value")
        dark_min = dark_data.get("min_value")
        print(f"Max sensor reading for white (lower is brighter) = {light_max}.")
        print(f"Min sensor reading for black = {dark_min}.")
        recomend_light = light_max
        if dark_min - recomend_light > 40:
            recomend_dark = recomend_light + 40
        else:
            recomend_dark = round(recomend_light + ((dark_min - recomend_light) / 3))
        if recomend_dark - recomend_light < 5:
            print(
                "Error: Cannot recommend thresholds:",
                "light and dark measurements may be too close for accurate frame detection",
            )
        else:
            log.info(f"Recommended thresholds: Light = {recomend_light}, Dark = {recomend_dark}.")
            log.info("Sending thresholds to device...")
            self.recomend_dark = recomend_dark
            self.recomend_light = recomend_light
            self.set_thresholds(light=recomend_light, dark=recomend_dark)
            print("Done")


def get_and_set_thresholds():
    params = iblrig.params.load_params_file()

    for k in params:
        if "F2TTL" in k and params[k] is None:
            log.error(f"Missing parameter {k}, please calibrate the device.")
            raise (KeyError)

    dev = Frame2TTL(params["COM_F2TTL"])
    dev.set_thresholds(dark=params["F2TTL_DARK_THRESH"], light=params["F2TTL_LIGHT_THRESH"])
    log.info("Frame2TTL: Thresholds set.")
    return 0


class Frame2TTLv2(Frame2TTL):
    def __init__(self, serial_port) -> None:
        self.serial_port = serial_port
        self.connected = False
        self.hw_version = None
        self.ser = self.connect()
        self.streaming = False

        self._dark_threshold = -150
        self._light_threshold = 150
        self.recomend_black = None
        self.recomend_white = None
        self.auto_dark = None  # Result of the auto threshold procedure from device
        self.auto_light = None  # Result of the auto threshold procedure from device
        self.manual_dark = None  # Reimplementation of threshold procedure locally
        self.manual_light = None  # Reimplementation of threshold procedure locally

    @property
    def light_threshold(self) -> int:
        return self._light_threshold

    @light_threshold.setter
    def light_threshold(self, value: int) -> None:
        """Set the light threshold
        Command: 5 bytes | [b"T", (light_threshold (uint16), dark_threshold (uint16))]
        Response: None
        """
        self.ser.write(struct.pack("<BHH", b"T", value, self.dark_threshold))
        self._light_threshold = value

    @property
    def dark_threshold(self) -> int:
        return self._dark_threshold

    @dark_threshold.setter
    def dark_threshold(self, value: int) -> None:
        """Set the dark threshold
        Command: 5 bytes | [b"T", (light_threshold (uint16), dark_threshold (uint16))]
        Response: None
        """
        self.ser.write(struct.pack("<BHH", b"T", self.light_threshold, value))
        self._dark_threshold = value

    def connect(self) -> serial.Serial:
        """Create connection to serial_port
        Perform a handshake and confirm it's a version 2 device
        """
        ser = serial.Serial(port=self.serial_port, baudrate=115200, timeout=3.0, write_timeout=1.0)
        self.connected = ser.isOpen()
        # Handshake
        # ser.write(struct.pack("c", b"C"))
        ser.write(b"C")
        # 1 byte response expected (unsigned)
        handshakeByte = int.from_bytes(ser.read(1), byteorder="little", signed=False)
        if handshakeByte != 218:
            raise serial.SerialException("Handshake with F2TTL device failed")
        # HW version
        # ser.write(struct.pack("c", b"#"))
        ser.write(b"#")
        # 1 byte response expected (unsigned)
        self.hw_version = int.from_bytes(ser.read(1), byteorder="little", signed=False)
        if self.hw_version != 2:
            raise serial.SerialException("Error: Frame2TTLv2 requires hardware version 2.")
        return ser

    def close(self) -> None:
        """Close connection to serial port"""
        self.ser.close()
        self.connected = self.ser.isOpen()

    def start_stream(self) -> None:
        """Enable streaming to USB (stream rate 100Hz? sensor samples at 20kHz)
        minicom --device /dev/ttyACM0 --baud 115200
        response = int.from_bytes(self.ser.read(4), byteorder='little')"""
        # char "S" plus 1 byte [0, 1] (uint8)
        # self.ser.write(struct.pack("cB", b"S", 1))
        self.ser.write(b"S" + int.to_bytes(1, 1, byteorder="little", signed=False))
        self.streaming = True

    def stop_stream(self) -> None:
        """Disable streaming to USB"""
        # char "S" plus 1 byte [0, 1] (uint8)
        # self.ser.write(struct.pack("cB", b"S", 0))
        self.ser.write(b"S" + int.to_bytes(1, 0, byteorder="little", signed=False))
        self.streaming = False

    def read_sensor(self, nsamples: int = 1) -> int:
        """Reads N contiguous samples from the sensor (raw data)
        Command: 5 bytes | [b"V" (uint8), nSamples (uint32)]
        Response: 2 bytes * nsamples | [sensorValue (uint16) * nsamples]
        """
        # self.ser.write(struct.pack("cB", b"V", nsamples))
        self.ser.write(b"V" + int.to_bytes(nsamples, 4, byteorder="little", signed=False))
        dt = np.uint16
        dt = dt.newbyteorder("<")
        values = np.frombuffer(self.ser.read(nsamples * 2), dtype=dt)
        return values

    def read_value(self) -> int:
        """Read one value from sensor (current)"""
        return self.read_sensor()

    def measure_black(self, mode="auto"):
        """Measure black levels and calculate light threshold.
        Command: 1 bytes | b"L" (uint8)
        Response: 2 bytes | value (int16)
        """
        if mode == "auto":
            # Run the firmware routine to find the light threshold
            self.ser.write(b"L")
            time.sleep(3)
            threshold = int.from_bytes(self.ser.read(2), byteorder="little", signed=True)
            self.auto_light = threshold
        elif mode == "manual":
            arr = self.read_sensor(20000)
            threshold = self._calc_threshold(arr, light=True)
            self.manual_light = threshold

    def measure_white(self, mode="auto"):
        """Measure white levels and calculate dark threshold.
        Command: 1 bytes | b"D" (uint8)
        Response: 2 bytes | value (int16)
        """
        if mode == "auto":
            # Run the firmware routine to find the dark threshold
            self.ser.write(b"D")
            time.sleep(3)
            threshold = int.from_bytes(self.ser.read(2), byteorder="little", signed=True)
            self.auto_dark = threshold
        elif mode == "manual":
            arr = self.read_sensor(20000)
            threshold = self._calc_threshold(arr, light=False)
            self.manual_dark = threshold

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
            out = np.min(mean_diffs) * 2
        if light:
            out = np.max(mean_diffs) * 1.5
        return out

    def calc_recomend_thresholds(self):
        """Calculate recomended light and dark thresholds for the sensor
        from the auto and manual measurments and calculations.
        """
        if (
            (self.auto_dark is None)
            or (self.auto_light is None)
            # or (self.manual_dark is None)
            # or (self.manual_light is None)
        ):
            log.error("Not all sensor measurments present")
            return -1

        # Check if manual and auto recomendations are similar
        assert np.allclose(self.auto_dark, self.manual_dark, atol=100)
        assert np.allclose(self.auto_light, self.manual_light, atol=100)
        self.recomend_dark = self.auto_dark
        self.recomend_light = self.auto_light

        if self.auto_dark > self.self.auto_light:
            log.error("Something looks wrong with the thresholds!"),
            log.error("Dark threshold must be lower than light threshold")
            log.error(f"Dark = {self.auto_dark}, Light = {self.auto_light}")
            return -1
        else:
            log.info("Recommended thresholds:")
            log.info(f"Light ={self.recomend_light}, Dark = {self.recomend_dark}.")
            print("Recommended thresholds not set yet. Pleas callset_recommendations()")
            return self.recomend_dark, self.recomend_light

    def set_thresholds(self, dark=None, light=None) -> None:
        """Set light, dark, or both thresholds for the device"""
        if dark is None:
            dark = self.recomend_dark
        if light is None:
            light = self.recomend_light

        # Device wants light threshold before dark
        if dark != self.dark_threshold:
            log.info(f"Setting dark threshold to {dark}")
        if light != self.light_threshold:
            log.info(f"Setting light threshold to {light}")
        if dark == -150 and light == 150:
            log.info(f"Resetting to default values: light={light} - dark={dark}")
        self.dark_threshold = dark
        self.light_threshold = light

    def set_recommendations(self):
        log.info("Sending thresholds to device...")
        self.set_thresholds(dark=self.recomend_dark, light=self.recomend_light)

    def __repr__(self) -> str:
        return f"""
            Bpod Frame2TTL device version 2.0
            Serial port:        {self.serial_port}
            Connected:          {self.connected}
            Streaming:          {self.streaming}
            Dark Threshold:     {self.dark_threshold}
            Light Threshold:    {self.light_threshold}"""

    def __del__(self):
        self.close()


if __name__ == "__main__":
    com_port = "COM4"
    f = Frame2TTL(com_port)
    # print(f.read_value())
    # print(f.measure_photons())
    # f.set_thresholds()
    # f.set_thresholds(light=41, dark=81)
    # f.set_thresholds(light=41)
    # f.set_thresholds(dark=81)
    # f.suggest_thresholds()
    # print(".")
