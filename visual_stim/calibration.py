# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, October 16th 2018, 12:13:00 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 16-10-2018 12:13:25.2525
import serial



if __name__ == '__main__':
    frame2ttl = '/dev/ttyACM1'
    ser = serial.Serial(port=frame2ttl, baudrate=115200, timeout=1)
    x = 0
    out = []
    ser.write(b'S')  # Start the stream
    while x < 100:
        # ser.write(b'V')  # ord('V')
        # ser.flushOutput()
        out.append(ser.read(4))
        print(out[x])
        x += 1

    out = [int.from_bytes(x, byteorder='little') for x in out]

    ser.write(b'S')  # Stop the stream
    ser.close()
    print('Done!')
