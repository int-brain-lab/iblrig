import numpy as np

bla = np.fromfile(
    r'C:\iblscripts\deploy\videopc\bonsai\workflows\test.bin', dtype=np.float64
)

print(len(bla))
print(len(bla) % 4)
try:
    rows = int(len(bla) / 4)
    ble = np.reshape(bla.astype(np.int64), (rows, 4))
except Exception:
    print(404)
