import numpy as np

from iblrig.frame2TTL import Frame2TTLv2

COM_PORT = 'COM'
f2ttl = Frame2TTLv2('/dev/ttyACM0')

light_thresh = 24.8
dark_thresh = -17.7

f2ttl.set_thresholds(light_thresh, dark_thresh)

## %% Compute thresholds
light = f2ttl.read_sensor(20000).astype(np.int32)
dark = f2ttl.read_sensor(20000).astype(np.int32)
dark_rms = np.sqrt(np.mean((dark - np.mean(dark)) ** 2))  # 43 centered on 2350
light_rms = np.sqrt(np.mean((light - np.mean(light)) ** 2))  # 42 centered on 4500

light_thresh = np.max(np.convolve(np.diff(dark), np.ones(20) / 20)) * 2
dark_thresh = np.min(np.convolve(np.diff(light), np.ones(20) / 20)) * 1.5

# fig, ax = plt.subplots()
# ax.plot(dark, label='dark')
# ax.plot(light, label='light')

# fig, ax = plt.subplots()
# ax.plot(np.diff(dark), label='dark')
# ax.plot(np.diff(light), label='light')
