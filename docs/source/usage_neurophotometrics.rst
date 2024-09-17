Neurophotometrics recording with iblrigv8
=========================================

This document describes how to use the iblrigv8 software to record Photometry using Neurophotometrics FP3002 system.

Setup
-----

- iblrigv8 is installed according to the instructions
- `settings/iblrig_settings.yaml` file is configured with the local folder and remote folder for the data transfer.
- `settings/hardware_settings.yaml` file is configured with the neurophotometrics device

.. code:: yaml
    RIG_NAME: photometry
    MAIN_SYNC: False
    device_neurophotometrics:
      BONSAI_WORKFLOW: devices/neurophotometrics/FP3002.bonsai
      COM_NEUROPHOTOMETRY: 'COM3'


Starting a task
---------------

- Start the Bonsai workflow by running the following command in powershell:
.. code:: powershell

   cd C:\iblrigv8\
   venv\scripts\Activate.ps1
   start_neurophotometrics
- in Bonsai click on the FP3002 node and load the desired photometry settings file
- start the task

The task will start and the photometry data will be saved in the data local folder with the following stucture:
- {local_data_folder}\neurophotometrics\yyyy-mm-dd\THHMMSS
Where yyyy-mm-dd is the date of the recording and HHMMSS is the time of the recording.


Copy command
------------

Usage
~~~~~

To initiate the data transfer from the local server to the remote server, open a terminal and type.

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data --tag photometry

The transfer local and remote directories are set in the
``iblrig/settings/iblrig_settings.py`` file.

