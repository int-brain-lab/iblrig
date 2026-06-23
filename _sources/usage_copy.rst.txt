
Copy commands
=============

Usage
-----

To initiate the data transfer from the local server to the remote
server, open a terminal and type.

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data --tag behavior

The transfer local and remote directories are set in the
``iblrig/settings/iblrig_settings.py`` file.

To copy data at another acquisition PC, such as video and ephys, use the relevant tag, e.g.

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data --tag video

NB: By default the local data that was copied over 2 weeks ago will be automatically removed. To
avoid this set the cleanup-weeks argument to -1:

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data behavior --cleanup-weeks -1

See the 'Clean-up local data' section on how to remove data without calling the copy script.

To view the copy status of your local sessions without actually copying, use the 'dry' argument:

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data behavior --dry

For more information on the tranfer_data arguments, use the help flag:

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   transfer_data --help


Clean-up local data
-------------------

To remove sessions fully copied to the server and older than 2 weeks,
open a terminal and type:

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   remove-old-sessions

Note: the server needs to be up and running or the sessions won’t be
verified as copied.


Behind the Copy Scripts
-----------------------

Workflow
~~~~~~~~

1. **Initial Stub Creation:** At the start of acquisition, an incomplete
   experiment description file - a *‘stub’* - is saved to the session
   on, both, the local PC and the lab server in a subfolder called
   ``_devices``. The filename of the stub includes the PC’s identifier,
   allowing the copy script to identify its source.

2. **Executing the Copy Script:** The copy script is executed on each
   acquisition PC independently and in no particular order.

3. **Navigating Local Session Data:** The script systematically
   navigates through local session folders (or optionally a separate
   ``transfers`` folder) that contain ``experiment.description`` stubs.

4. **Skipping Transferred Sessions:** The script ignores session folders
   containing a file named ``transferred.flag`` (see 7).

5. **Copying Collections:** For each session, the script reads the
   respective stub and uses ``rsync`` to copy each ``collection``.
   Subfolders not specified under a ``collection`` key are omitted from
   copying.

6. **Removing Remote Stubs:** Upon successful copying, the remote stub
   file is merged with the remote ``experiment.description`` file (or
   copied over if one doesn’t exist already). The remote stub file is
   then deleted.

7. **Confirming Transfer Locally:** A ``transferred.flag`` file is
   created in the local session folder to confirm the transfer’s
   success.

8. **Completion and Cleanup:** Once no more remote stub files exist
   for a given session, the empty ``_devices`` subfolder is removed.
   Additionally, a ‘raw_session.flag’ file is created in the remote session folder,
   indicating the successful transfer of all files.

Example of workflow
~~~~~~~~~~~~~~~~~~~

Example of three sessions each in a different copy state:

* The State on the Remote Lab Server
  ::

     lab server/
     └── subject/
         └── 2020-01-01/
             ├── 001/
             │   └── _devices/
             │       ├── 2020-01-01_1_subject@taskPC.yaml
             │       └── 2020-01-01_1_subject@ephysPC.yaml
             ├── 002/
             │   ├── _ibl_experiment.description.yaml
             │   ├── raw_task_data_00/
             │   └── _devices/
             │       └── 2020-01-01_1_subject@ephysPC.yaml
             └── 003/
                 ├── raw_task_data_00/
                 ├── raw_ephys_data/
                 ├── _ibl_experiment.description.yaml
                 └── raw_session.flag


* The State on the Local Task Acquisition PC
  ::

     acquisition computer (taskPC)/
     └── subject/
         └── 2020-01-01/
             ├── 001/
             │   ├── raw_task_data_00/
             │   └── _ibl_experiment.description_taskPC.yaml
             ├── 002/
             │   ├── raw_task_data_00/
             │   ├── _ibl_experiment.description_taskPC.yaml
             │   └── transferred.flag
             └── 003/
                 ├── raw_task_data_00/
                 ├── folder_not_in_desc_file/
                 ├── _ibl_experiment.description_taskPC.yaml
                 └── transferred.flag


* The State on the Local Ephys Acquisition PC
   ::

     acquisition computer (ephysPC)/
     └── subject/
         └── 2020-01-01/
             ├── 001/
             │   ├── raw_ephys_data/
             │   └── _ibl_experiment.description_ephysPC.yaml
             ├── 002/
             │   ├── raw_ephys_data/
             │   ├── _ibl_experiment.description_ephysPC.yaml
             └── 003/
                 ├── raw_ephys_data/
                 ├── folder_not_in_desc_file/
                 ├── _ibl_experiment.description_ephysPC.yaml
                 └── transferred.flag

With the lab server and acquisition pcs in the states above, the
sessions are in the following states

* ``subject/2020-01-01/001`` no data have been copied.
* ``subject/2020-01-01/002`` data from *taskPC* have been copied, data from *ephysPC* remains to be copied.
* ``subject/2020-01-01/003`` data copied from all acquisition PCs.
