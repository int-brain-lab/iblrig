# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, October 16th 2018, 12:13:00 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 16-10-2018 12:13:25.2525
import serial
from pythonosc import udp_client
import time
import sys
import threading


class Frame2TTLReader(object):
    def __init__(self, comport='COM6'):
        self.osc_client = udp_client.SimpleUDPClient('127.0.0.1', 6667)
        self.frame2ttl = comport  # /dev/ttyACM1'
        self.ser = serial.Serial(
            port=self.frame2ttl, baudrate=115200, timeout=1)
        self.ser.write(b'S')  # Start the stream, stream rate 100Hz
        self.ser.write(b'S')  # Start the stream, stream rate 100Hz
        self.read = True

    def read_and_send_data(self):
        i = 0
        while self.read:
            d = self.ser.read(4)
            d = int.from_bytes(d, byteorder='little')
            self.osc_client.send_message("/d", d)
            i += 1
            if i == 100:
                self.osc_client.send_message("/i", i)
                i = 0
            print(i, d)


    def stop(self):
        self.read = False
        print('Done!')


def main(comport):
    obj = Frame2TTLReader(comport)
    return obj

if __name__ == '__main__':
    # main(sys.argv[1])
    comport = 'COM6'
    obj = Frame2TTLReader(comport)
    print('.')