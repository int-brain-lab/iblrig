************************************
Running video on a separate computer
************************************

Video can be run on a separate computer, which is recommended when recording multiple cameras.


Setup
=====

Installing drivers
------------------

Both spinnaker and pyspin must be installed before running an experiment:

.. code:: powershell

   cd C:\iblrigv8\
   venv\scripts\Activate.ps1
   install_spinnaker
   install_pyspin


Settings config
---------------

The camera acquisition is configured by parameters in the 'device_cameras' key  of the `hardware_settings.yaml` file.
Below is an overview of the parameters:

.. code:: yaml

   device_cameras:
     # The name of the configuration. This is passed to the CLI.
     default:
       # This is required: the Bonsai workflows to be called by the CLI script.
       BONSAI_WORKFLOW:
         # Optional setup (e.g. alignment) workflow
         setup: devices/camera_setup/EphysRig_SetupCameras.bonsai
         # Required workflow to be called when the experiment starts
         recording: devices/camera_recordings/TrainingRig_SaveVideo_TrainingTasks.bonsai
       # Camera #1 name
       left:
         # Required camera device index (assigned in driver software)
         INDEX: 1
         # Optional expected frame height. Actual resolution should be set in the driver software.
         HEIGHT: 1024
         # Optional expected frame width. This is simply used in QC.
         WIDTH: 1280
         # Optional expected frame rate (Hz). This is simply used in QC.
         FPS: 30

Multiple configurations can be added, e.g. 'default', 'training', 'ephys', etc. and within each, multiple cameras
can be added, e.g. 'left', 'right', 'body', etc.  Each configuration requires a `BONSAI_WORKFLOW: recording` key;
each camera requires an `INDEX` key.


Starting a task
===============

Below shows how to start the cameras for the subject 'example' with configuration 'default':

.. code:: powershell

   cd C:\iblrigv8\
   venv\scripts\Activate.ps1
   start_video_session example default

Copy command
=============

Usage
-----

To initiate the data transfer from the local server to the remote server, open a terminal and type.

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data video

The transfer local and remote directories are set in the
``iblrig/settings/iblrig_settings.py`` file.
