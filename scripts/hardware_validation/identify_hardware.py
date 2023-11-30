import array
import glob
import sys

from serial import Serial, SerialException

if sys.platform.startswith('win'):
    ports = ['COM%s' % (i + 1) for i in range(256)]
elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
    # this excludes your current terminal "/dev/tty"
    ports = glob.glob('/dev/tty[A-Za-z]*')
elif sys.platform.startswith('darwin'):
    ports = glob.glob('/dev/tty.*')
else:
    raise OSError('Unsupported platform')


def query(s_obj, req, n=1):
    s_obj.write(req)
    return s.read(n)


for port in ports:
    try:
        s = Serial(port, timeout=0.1)
        m = 'unknown'
        v = None

        for trial in range(4):
            s.flush()
            if trial == 0 and query(s, b'6') == b'5':
                v = array.array('H', query(s, b'F', 4))
                match v[1]:
                    case 1:
                        hw = '0.5'
                    case 2:
                        hw = 'r0.7+'
                    case 3:
                        hw = 'r2.0-2.5'
                    case 4:
                        hw = '2+ r1.0'
                    case _:
                        hw = '(unknown version)'
                m = f'Bpod {hw}, firmware {v[0]}'
                s.write(b'Z')
                break
            elif trial == 1 and query(s, b'C') == (218).to_bytes(1, 'little'):
                v = 2 if len(query(s, b'#')) > 0 else 1
                m = f'frame2ttl, v{v}'
                break
            elif trial == 2 and len(query(s, b'Q', 2)) > 1 and query(s, b'P00', 1) == (1).to_bytes(1, 'little'):
                v = '2+' if query(s, b'I') == (0).to_bytes(1, 'little') else 1
                m = f'rotary encoder module, v{v}'
                break
            elif trial == 3:
                pass

        s.flush()
        s.close()
        print(f'{s.portstr}: {m}')
    except (OSError, SerialException):
        pass
