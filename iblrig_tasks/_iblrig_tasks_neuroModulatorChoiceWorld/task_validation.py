# first read jsonable file containing the trials in record oriented way
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from iblutil.io import jsonable

task_data = jsonable.read('/Users/olivier/Downloads/D6/_iblrig_taskData.raw.jsonable')

# pop-out the bpod data from the table
bpod_data = []
for td in task_data:
    bpod_data.append(td.pop('behavior_data'))

# and convert the remaining dictionary in a proper table format
task_data = pd.DataFrame(task_data)

## %%
# from the bpod data, we create columns that contain the time elapsed during reward and delays
task_data['bpod_valve_time'] = 0
task_data['bpod_delay'] = 0
for i, bp in enumerate(bpod_data):
    sts = bp['States timestamps']
    task_data.at[i, 'bpod_valve_time'] = np.diff(sts['reward'] if 'reward' in sts else np.NaN)
    task_data.at[i, 'bpod_delay'] = np.nansum(
        np.r_[
            np.diff(sts['delay_reward'])[0] if 'delay_reward' in sts else 0,
            np.diff(sts['delay_error'])[0] if 'delay_error' in sts else 0,
            np.diff(sts['delay_nogo'])[0] if 'delay_nogo' in sts else 0,
        ]
    )

## %%
# if all checks out the valve time should almost proportional to the reward amound
r = np.corrcoef(
    task_data['reward_amount'][~np.isnan(task_data['valve_time'])], task_data['valve_time'][~np.isnan(task_data['valve_time'])]
)
assert r[0, 1] >= 0.9999

# the other test is to check that we have delays - this fails on data collected 27/01/2023
# here the rewarded trials have no delay. Oups...
assert np.all(task_data['bpod_delay'] >= 1.5)

## %%
plt.figure()
plt.plot(task_data['reward_amount'].values, task_data['valve_time'].values, '.')
plt.figure()
plt.plot(task_data['bpod_delay'])
plt.show()
