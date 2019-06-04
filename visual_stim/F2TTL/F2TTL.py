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
        ser = serial.Serial(port=serial_port, baudrate=115200, timeout=1)
        self.connected = True
        return ser

    def measure_light(self, num_samples=250):
        sample_sum = 0
        for i in range(num_samples):
            sample_sum += self.read_value()

        mean_value = sample_sum / num_samples

        return mean_value

    def set_threshold(self, light=None, dark=None):
        if light is None:
            light = self.light_threshold
        if dark is None:
            dark = self.dark_threshold

        self.ser.write(b'C')
        response = int.from_bytes(self.ser.read(1), byteorder='little')
        if response != 218:
            raise(ConnectionError)

        self.ser.write(struct.pack('cII', b'T', light, dark))
        if light != self.light_threshold:
            print(f"Light threshold set to {light}")
        if dark != self.dark_threshold:
            print(f"Dark threshold set to {dark}")
        if light == 40 and dark == 80:
            print(f"Resetted to default values: light={light} - dark={dark}")
        self.light_threshold = light
        self.dark_threshold = dark
        return

    def read_value(self):
        self.ser.write(b'V')
        response = self.ser.read(4)
        # print(np.frombuffer(response, dtype=np.uint32))
        response = int.from_bytes(response, byteorder='little')
        return response

    def stream(self):
        self.ser.write(b'S')  # Start the stream, stream rate 100Hz
        self.ser.write(b'S')  # Start the stream, stream rate 100Hz
        self.streaming = not self.streaming

        # while self.streaming:
        #     response = int.from_bytes(self.ser.read(4), byteorder='little')
        #     print(response)
        # self.ser.write(b'S')  # Start the stream, stream rate 100Hz


if __name__ == "__main__":
    com_port = '/dev/ttyACM1'
    f = frame2TTL(com_port)
    print(f.read_value())
    print(f.measure_light())
    f.set_threshold()
    f.set_threshold(light=41, dark=81)
    f.set_threshold(light=41)
    f.set_threshold(dark=81)
    print('.')
