import nidaqmx
from nidaqmx.constants import (
    AcquisitionType,
    Edge,
    TerminalConfiguration,
    VoltageUnits,
)  # Signal

import numpy as np

device = "Dev1"
sampling_freq = 1000
buffer_size = 1000
global out
out = np.array([])


def callback(task_handle, every_n_samples_event_type, number_of_samples, callback_data):
    global out
    print(task_handle)
    print(every_n_samples_event_type)
    print(number_of_samples)
    print(callback_data)
    samples = task.read(number_of_samples)
    out = np.append(out, samples, axis=None)
    print(f"{int(len(out) / number_of_samples)}...", end="", flush=True)
    return 0


def digital_callback(task_handle, signal_type, callback_data):
    print(task_handle, signal_type, callback_data)
    samples = task.read(buffer_size)
    out.extend(samples)
    print(f"{int(len(out)/buffer_size)}...", end="", flush=True)
    return 0


def done_callback(task_handle, status, callback_data):
    print("Status", status)
    return 0


if __name__ == "__main__":

    # Set pmt gain
    # pmt_gain = 0.5
    # with nidaqmx.Task() as task:
    #     task.ao_channels.add_ao_voltage_chan(f"/{device}/ao1","",0,1.25)
    #     task.write(pmt_gain)

    # Start recording task
    task = nidaqmx.Task(new_task_name="ReaderTask")

    task.ai_channels.add_ai_voltage_chan(
        f"/{device}/ai0",
        name_to_assign_to_channel="",
        terminal_config=TerminalConfiguration.DEFAULT,
        min_val=0,
        max_val=10,
        units=VoltageUnits.VOLTS,
        custom_scale_name="",
    )

    task.timing.cfg_samp_clk_timing(
        sampling_freq,
        source="",
        active_edge=Edge.RISING,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=buffer_size,
    )
    task.register_every_n_samples_acquired_into_buffer_event(buffer_size, callback)
    task.register_done_event(done_callback)

    task.start()
    input("Running task. Press Enter to stop. Seconds elapsed: \n")
    task.stop()

    print(len(out))
    print(len(out) % buffer_size)

    # out = {'data': [], 'n': 0}
    # task = nidaqmx.Task()

    # task.di_channels.add_di_chan("Dev1/port0/line0")
    # task.register_signal_event(Signal.SAMPLE_CLOCK, digital_callback)
    # task.timing.cfg_samp_clk_timing(
    #     sampling_freq,
    #     source="",
    #     active_edge=Edge.RISING,
    #     sample_mode= AcquisitionType.FINITE,
    #     samps_per_chan=1000)
