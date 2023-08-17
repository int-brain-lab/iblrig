# Using IBLRIG

## Run a task
### Through the graphical user interface

To run a task using the graphical user interface, open a terminal and type in the following:

    C:\iblrigv8\venv\scripts\Activate.ps1
    iblrig

The *IBL Rig Wizard* GUI window will pop open:![gui.png](gui.png)

1.  Enter your Alyx username & click connect

    This will populate the GUI's fields with the entries relevant to your lab.

2.  Select the desired values.
    
    Use the *Filter* field to quickly narrow down the displayed subjects.
    
3.  Hit *Start* and off you go.


There are some additional controls in the *Flow* section:

-   When checking *Append* before pressing *Start*, the task will be joined to the previous task - resulting in chained tasks.

-   The *Flush* button will toggle the valve for cleaning purposes.
     

    




### Command Line
To run a task using command line, open a terminal and activate the environment and set current directory.

    C:\iblrigv8\venv\scripts\Activate.ps1
    cd C:\iblrigv8\

#### Running a single task

    python .\iblrig_tasks\_iblrig_tasks_trainingChoiceWorld\task.py --subject algernon --user john.doe

#### Chain several tasks together
You can feed the `append` flag to the task to chain several tasks together.  For example, to run a passive task after an ephys task, you can do:

    python .\iblrig_tasks\_iblrig_tasks_ephysChoiceWorld\task.py --subject algernon

Followed by:

    python .\iblrig_tasks\_iblrig_tasks_passiveChoiceWorld\task.py --subject algernon --append


### Flush valve

To flush valve 1 of the Bpod, enter

    flush

Press ENTER to close the valve.

## Copy commands

### Usage

To initiate the data transfer from the local server to the remote server, open a terminal and type.

    C:\iblrigv8\venv\scripts\Activate.ps1
    transfer_data

The transfer local and remote directories are set in the `iblrig/settings/iblrig_settings.py` file.

### Clean-up local data

To remove sessions fully copied to the server and older than 2 weeks, open a terminal and type:

    C:\iblrigv8\venv\scripts\Activate.ps1
    remove-old-sessions

Note: the server needs to be up and running or the sessions won't be verified as copied.

### Installation
If you get missing libraries, you can install the iblscripts package with

    pip install git+https://github.com/int-brain-lab/iblscripts.git



## FAQ
Section here with common copy errors and how to fix them

## Behind the copy scripts

### Workflow
1. At the start of acquisition an incomplete experiment description file (a 'stub') is saved on
the local PC and in the lab server, in a session subfolder called `_devices`.  The filename
includes the PC's identifier so the copy script knows which stub was saved by which PC.
2. The copy script is run on each acquisition PC in any order.
3. The script iterates through the local session data (or optionally a separate 'transfers'
folder) that contain experiment.description stubs.
4. Session folders containing a 'transferred.flag' file are ignored. 
5. For each session, the stub file is read in and rsync is called for each `collection`
contained.  If there is a local subfolder that isn't specified in a `collection` key, it won't
be copied.
6. Once rsync succeeds, the remote stub file is merged with the remote experiment.description
file (or copied over if one doesn't already exist).  The remote stub is deleted. 
7. A `transferred.flag` file is created in the local session folder.
8. If no more remote stub files exist for a given session, the empty _devices subfolder is
deleted and a 'raw_session.flag' file is created in the remote session folder.

### Example of workflow
Example of three sessions each in a different copy state:

#### Lab server
The state on the remote lab server
```
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
```

#### Task acquisition PC
The state on the local task acquisition PC
```
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
```
#### Ephys acquisition PC
The state on the local ephys acquisition PC
```
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
```

#### Copy status
With the lab server and acquisition pcs in the states above, the sessions are in the following
states
```
- subject/2020-01-01/001 - no data have been copied.
- subject/2020-01-01/002 - data from 'taskPC' have been copied, data from 'ephysPC' remains to be copied.
- subject/2020-01-01/003 - data copied from all acquisition PCs.
```