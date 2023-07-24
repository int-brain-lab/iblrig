import sys
import glob
from serial import Serial, SerialException


if sys.platform.startswith('win'):
    ports = ['COM%s' % (i + 1) for i in range(256)]
elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
    # this excludes your current terminal "/dev/tty"
    ports = glob.glob('/dev/tty[A-Za-z]*')
elif sys.platform.startswith('darwin'):
    ports = glob.glob('/dev/tty.*')
else:
    raise EnvironmentError('Unsupported platform')

result = []
for port in ports:
    try:
        s = Serial(port)
        print(port)
        s.write(b"S")
        print(s.read)
        s.write(b"#")
        print(s.read)
        s.close()
        result.append(port)
        print('')
    except (OSError, SerialException):
        pass

print(result)