import time

import nidaqmx
import numpy as np
from nidaqmx.constants import AcquisitionType, Edge, TerminalConfiguration, VoltageUnits
from pathlib import Path
import os


# %matplotlib auto
# fig = plt.figure()
# ax1 = fig.add_subplot(211)
# ax2 = fig.add_subplot(212)

fpath = r"C:\Users\User\Desktop\scratch_bonsai-harp\NIdata.bin"
data = np.fromfile(fpath, dtype=np.float64)

nsamples = 1024
sample_frequency = 1000
# freqs = np.linspace(0, int(sample_frequency / 2), int(nsamples / 2 + 1))

# task = nidaqmx.Task()
# with nidaqmx.Task() as task:
#     task.di_channels.add_di_chan(
#         "Dev1/port0/line0",
#     )
#     task.timing.cfg_samp_clk_timing(
#         sample_frequency, active_edge=Edge.RISING,
#         sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=nsamples
#     )
#     # task.start()
#     # task.stop()


with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan(
        "Dev1/ai0",
        terminal_config=TerminalConfiguration.RSE,
        min_val=-5.0,
        max_val=5.0,
        units=VoltageUnits.VOLTS,
    )
    task.timing.cfg_samp_clk_timing(
        sample_frequency,
        active_edge=Edge.RISING,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=1000,
    )

    fpath = Path(r"C:\iblrig_data\test.npy")
    with fpath.open("ab") as f:
        # task.start()
        # task.stop()
        tstart = time.time()
        tend = time.time()
        while tend - tstart < 4:
            t1 = time.time()
            data = task.read(number_of_samples_per_channel=4096)
            t2 = tend = time.time()
            tdata = np.array(data)
            np.save(f, tdata)
            # tdata -= np.mean(tdata)
            # ffto = np.fft.fft(tdata)
            # ffto = np.abs(ffto)
            # ffto = ffto[0 : (int(nsamples / 2) + 1)]

            # ax1.clear()
            # ax2.clear()
            # ax1.plot(data)
            # ax2.plot(freqs, ffto)
            # fig.show(0)
            # plt.pause(0.000000001)
            # t3 = int(round(time.time() * 1000))
            print(f"t2-t1 = {t2 - t1}s")


with fpath.open("rb") as f:
    fsz = os.fstat(f.fileno()).st_size
    out = np.load(f)
    while f.tell() < fsz:
        out = np.vstack((out, np.load(f)))

fpath.unlink()
print(out.shape)
