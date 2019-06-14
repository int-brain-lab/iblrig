import serial
import numpy as np
import struct


class frame2TTL(object):
    def __init__(self, serial_port):
        self.serial_port = serial_port
        self.light_threshold = 40
        self.dark_threshold = 80
        self.connected = False
        self.ser = self.connect(serial_port)
        self.streaming = False

    def connect(self, serial_port):
        """Create connection to serial_port"""
        ser = serial.Serial(port=serial_port, baudrate=115200, timeout=1)
        self.connected = True
        return ser

    def close(self):
        """Close connection to serial port"""
        self.ser.close()
        return

    def measure_light(self, num_samples: int = 250) -> dict:
        """Measure <num_samples> values from the sensor and return basic stats.
        Mean, Std, SEM, Nsamples
        """
        import time
        sample_sum = []
        for i in range(num_samples):
            sample_sum.append(self.read_value())
            time.sleep(0.001)

        out = {
            'mean_value': np.array(sample_sum).mean(),
            'max_value': np.array(sample_sum).max(),
            'min_value': np.array(sample_sum).min(),
            'std_value': np.array(sample_sum).std(),
            'sem_value':  np.array(sample_sum).std() / np.sqrt(num_samples),
            'nsamples': num_samples
        }
        return out

    def set_threshold(self, light=None, dark=None):
        """Set light, dark, or both thresholds for the device"""
        if light is None:
            light = self.light_threshold
        if dark is None:
            dark = self.dark_threshold

        self.ser.write(b'C')
        response = self.ser.read(1)
        if response[0] != 218:
            raise(ConnectionError)

        self.ser.write(struct.pack('<BHH', ord('T'), light, dark))
        if light != self.light_threshold:
            print(f"Light threshold set to {light}")
        if dark != self.dark_threshold:
            print(f"Dark threshold set to {dark}")
        if light == 40 and dark == 80:
            print(f"Resetted to default values: light={light} - dark={dark}")
        self.light_threshold = light
        self.dark_threshold = dark
        return

    def suggest_thresholds(self):
        reply = input(
            "Set pixels under Frame2TTL to white (rgb 255,255,255) and press enter >")
        print(" ")
        print("Measuring white...")
        lightData = self.measure_light(10000)

        reply = input(
            "Set pixels under Frame2TTL to black (rgb 0,0,0) and press enter >")
        print(" ")
        print("Measuring black...")
        darkData = self.measure_light(10000)
        print(" ")
        lightMax = lightData.get('max_value')
        darkMin = darkData.get('min_value')
        print(
            f"Max sensor reading for white (lower is brighter) = {lightMax}.")
        print(f"Min sensor reading for black = {darkMin}.")
        recommendedLightThreshold = lightMax
        if darkMin - recommendedLightThreshold > 40:
            recommendedDarkThreshold = recommendedLightThreshold + 40
        else:
            recommendedDarkThreshold = round(
                recommendedLightThreshold + ((darkMin - recommendedLightThreshold)/3))
        if recommendedDarkThreshold - recommendedLightThreshold < 5:
            print("Error: Cannot recommend thresholds; light and dark measurements may be too close for accurate frame detection")
        else:
            print(
                f"Recommended thresholds: Light = {recommendedLightThreshold}, Dark = {recommendedDarkThreshold}.")

    def read_value(self):
        """Read one value from sensor (current)"""
        self.ser.write(b'V')
        response = self.ser.read(4)
        # print(np.frombuffer(response, dtype=np.uint32))
        response = int.from_bytes(response, byteorder='little')
        return response

    def start_stream(self):
        """Enable streaming to USB"""
        self.ser.write(struct.pack('cB', b'S', 1))
        self.streaming = True

    def stop_stream(self):
        """Disable streaming to USB"""
        self.ser.write(struct.pack('cB', b'S', 0))
        self.streaming = False

        # while self.streaming:
        #     response = int.from_bytes(self.ser.read(4), byteorder='little')
        #     print(response)
        # self.ser.write(b'S')  # Start the stream, stream rate 100Hz


if __name__ == "__main__":
    com_port = '/dev/ttyACM0'
    f = frame2TTL(com_port)
    print(f.read_value())
    print(f.measure_light())
    f.set_threshold()
    f.set_threshold(light=41, dark=81)
    f.set_threshold(light=41)
    f.set_threshold(dark=81)
    print('.')
