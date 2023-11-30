# import numpy.polynomial.polynomial as poly
# from scipy.signal import find_peaks
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def find_calibration_files(folder_path: str) -> list:
    folder_path = Path(folder_path)
    files = [str(x) for x in folder_path.glob('*_iblrig_calibration_screen_*.raw.ssv')]
    return files


def raw_to_df(file_path):
    file_path = Path(file_path)
    df = pd.read_csv(file_path, sep=' ', header=None)
    df = df.drop(columns=4)
    df.columns = ['val', 'r', 'g', 'b']
    # # select which channel to use
    if 'screen_red' in file_path.name or 'screen_bright' in file_path.name:
        df = df.drop(columns=['b', 'g'])
    elif 'screen_green' in file_path.name:
        df = df.drop(columns=['r', 'b'])
    elif 'screen_blue' in file_path.name:
        df = df.drop(columns=['r', 'g'])
    df.columns = ['val', 'int']  # df.r

    # # Find first peak at start to remove the gray screen inputs
    # peaks, _ = find_peaks(df.val, height=df.val.mean()-df.val.sem())
    # init = peaks[0]
    # # # Cut the df to what's relevant reset index!
    # df = df[init:].reset_index()
    # df = df.drop(columns='index')
    return df


def fit_n_plot(df, fname=None):
    # Fit a polynomial
    x_new = np.round(np.linspace(0.01, 1, 100), 2)

    # coefs = poly.polyfit(df.int, df.val, 6)
    # ffit_vals = poly.polyval(x_new, coefs)
    # ffit = poly.Polynomial(coefs)

    if 'screen_red' in fname:
        c = 'red'
        label = 'Red channel'
    elif 'screen_green' in fname:
        c = 'green'
        label = 'Green channel'
    elif 'screen_blue' in fname:
        c = 'blue'
        label = 'Blue channel'
    elif 'screen_bright' in fname:
        c = 'gray'
        label = 'All channels'

    plt.plot(df.int, df.val, '.', c=c, label=label)
    # plt.plot(x_new, ffit(x_new), c=c)
    plt.plot(x_new, x_new, c='k')
    plt.show()


# if __name__ == "__main__":
folder_path = r'C:\iblrig\devices\screen_calibration'
folder_path = '/home/nico/Projects/IBL/github/iblrig/devices/screen_calibration'
files = find_calibration_files(folder_path)

# file_path = files[-1]
# plt.ion()
# for file_path in files:
#     df = raw_to_df(file_path)
#     fit_n_plot(df, fname=file_path)
# plt.title('Screen calibration')
# plt.legend()
# plt.xlabel('Intensity requested')
# plt.ylabel('frame2TTL raw output (lower is brighter)')
# plt.axhline(40, ls='--', alpha=0.5)
# plt.axhline(80, ls='--', alpha=0.5)

# folder_path = '/home/nico/Projects/IBL/github/iblrig/scratch/calibration/harp'

files = find_calibration_files(folder_path)

file_path = files[-1]
plt.figure()
x_new = np.round(np.linspace(0.01, 1, 100), 2)
for file_path in files:
    if 'screen_red' in file_path:
        c = 'red'
        label = 'Red channel'
    elif 'screen_green' in file_path:
        c = 'green'
        label = 'Green channel'
    elif 'screen_blue' in file_path:
        c = 'blue'
        label = 'Blue channel'
    elif 'screen_bright' in file_path:
        c = 'gray'
        label = 'All channels'
    df = raw_to_df(file_path)
    plt.plot(df.int, df.val, '.', c=c, label=label)
    plt.yscale('log')
    plt.xscale('log')
    plt.plot(x_new, x_new, c='k')
plt.title('Screen calibration')
plt.legend()
plt.xlabel('Intensity requested')
plt.ylabel('Photodiode raw output (lower is brighter)')
plt.show()
print('.')
# plt.axhline(40, ls='--', alpha=0.5)
# plt.axhline(80, ls='--', alpha=0.5)

# # df = raw_to_df(file_path)
# file_path = Path(file_path)
# df = pd.read_csv(file_path, sep=' ', header=None)
# df = df.drop(columns=4)
# df.columns = ['val', 'r', 'g', 'b']
# # # select which channel to use
# if 'screen_red' in file_path.name or 'screen_bright' in file_path.name:
#     df = df.drop(columns=['b', 'g'])
# df.columns = ['val', 'int']  # df.r

# fit_n_plot(df, fname=files[-1])

# df.val
