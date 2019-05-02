#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, October 16th 2018, 12:13:00 pm
import serial
from pythonosc import udp_client
import time

# osc_client = udp_client.SimpleUDPClient('127.0.0.1', 6667)

# frame2ttl = 'COM6'  # /dev/ttyACM1'
# ser = serial.Serial(port=frame2ttl, baudrate=115200, timeout=1)
# ser.write(b'S')  # Start the stream, stream rate 100Hz

# i = 0
# while True:
#     d = ser.read(4)
#     d = int.from_bytes(d, byteorder='little')
#     osc_client.send_message("/d", d)
#     i += 1
#     if i == 99:
#         osc_client.send_message("/i", 1)
#         i = 0




if __name__ == '__main__':
    osc_client = udp_client.SimpleUDPClient('127.0.0.1', 6667)

    frame2ttl = 'COM6'  # /dev/ttyACM1'
    ser = serial.Serial(port=frame2ttl, baudrate=115200, timeout=1)
    ser.write(b'S')  # Start the stream, stream rate 100Hz
    ser.write(b'S')  # Start the stream, stream rate 100Hz

    i = 0
    while True:
        d = ser.read(4)
        d = int.from_bytes(d, byteorder='little')
        osc_client.send_message("/d", d)
        i += 1
        if i == 100:
            osc_client.send_message("/i", i)
            i = 0


        print(i, d)
    print('Done!')
