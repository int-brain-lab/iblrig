# iblrig v7
Software used to interact with various pieces of specialized hardware for neuroscience data acquisition.

## Installation on Windows
Software has only been tested on Windows 10. No other version of Windows is supported at this time. The test user account has 
administrative rights.

### Prerequisite Software:
In order to install iblrig on a Windows machine please ensure that the following prerequisite is installed first.
- A fully featured text editor is recommended, something like [Notepad++](https://notepad-plus-plus.org/)
- [Git](https://git-scm.com); it is recommended to set notepad++ as your default editor for git

Manually download and install the software by following the links above. The other option is to follow the instructions below.

#### (Optional) Use chocolatey to install prerequisite software
[Chocolatey](https://chocolatey.org/) is a command line approach to bring package management to Window. Run the following 
commands from the **Administrator: Windows Powershell** prompt to install prerequisite software by this method:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
choco install notepadplusplus --yes
choco install git --params "/Editor:Notepad++ /NoShellIntegration" --yes
```
  - git commands will be unavailable until a new session is started; close the current **Administrator: Windows Powershell** 
prompt

### Installation Instructions:
- Ensure git and your favorite text editor are already installed by whatever method is desired
- Ensure a stable internet connection is present as several commands will require software to be downloaded
- There is no supported upgrade path from v6 to v7
- User account name is assumed to be `User`, please modify commands where appropriate
- The commands given below are assumed to be run on a 'clean' system
  - These instructions assume that `C:\iblrig` and `C:\iblrig_params` directories DO NOT exist; if these directories do 
    exist, it is recommended to back them up to something like `C:\iblrig_bkup` and `C:\iblrig_params_bkup`

Run the following commands from the non-administrative **Windows Powershell** prompt
```powershell
Set-ExecutionPolicy -Scope CurrentUser Unrestricted -Force
cd \
git clone https://github.com/int-brain-lab/iblrig
git clone https://github.com/int-brain-lab/iblpybpod
cd iblrig
git checkout rc
New-Item -ItemType Directory -Force -Path C:\Temp
Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe -OutFile C:\Temp\python-3.8.10-amd64.exe
Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.8.10-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"
C:\Users\User\AppData\Local\Programs\Python\Python38\.\python.exe -m venv C:\iblrig\venv
C:\iblrig\venv\Scripts\.\Activate.ps1
C:\iblrig\venv\scripts\python.exe -m pip install --upgrade pip wheel
pip install --editable . 
pip install --editable ..\iblpybpod
python setup_pybpod.py
cd Bonsai
powershell.exe .\install.ps1
```
  - NOTE: ONE is installed as part of the iblrig requirement. ONE will need to be configured for your use case. Please review 
the ONE [documentation](https://int-brain-lab.github.io/ONE/) for specifics on how to accomplish this. Then run the following 
command or something similar for your specific setup to test it is working: `python -c "from one.api import ONE; ONE()"`

### Configuring the iblrig_params.yml file for your setup
Open the `C:\iblrig\iblrig_params.yml` configuration file in your favorite text editor and change whatever the values to match 
your system. If following these instructions, the only two values that need to be updated should be: 
- iblrig_remote_data_path: "\\\\lab_server_ip_or_dns\\data_folder"
- iblrig_remote_server_path: "\\\\lab_server_ip_or_dns"
  - NOTE: When altering these values, be sure to keep in mind that the backslash character is also used as an escape character. 
This means that even though the `Windows File Explorer` may prefix the local lab server address with only two backslashes, we 
will need four backslashes in our `iblrig_params.yml` entry.

### Running pybpod
To run pybpod and begin data acquisition run the following commands from a non-administrative **Windows Powershell** prompt:
```powershell
C:\iblrig\venv\Scripts\.\Activate.ps1
cd C:\iblrig_params
start-pybpod
```

#### For easier launching of pybpod
Within the `C:\iblrig` folder there is a `start-pybpod-venv_Shortcut.lnk` file that can be copied to the desktop for ease of use. 
Running the following powershell command from a non-administrative **Windows Powershell** prompt will perform this copy operation:
```powershell
Copy-Item "C:\iblrig\start-pybpod-venv_Shortcut.lnk" -Destination "$Env:HOMEPATH\Desktop"
```

### Configuring bpod boards
When first running pybpod, ensure that the Bpod boards are configured for your current setup. If this was an 'upgrade' 
from a previous version of iblrig, and the recommended backup operation was performed; take special note of the values within 
the `C:\iblrig_params\.iblrig_params.json` file. These parameters will contain the values like board name and COM ports relevant 
to your system.    

#### Setup instructions for launching the 'Experiment Description GUI' prior to task launch (DEVELOP)
The 'Experiment Description GUI' is currently being developed in the iblscripts repo. This GUI is intended to simplify the 
categorization of an experiment and cleanly define what projects and procedures an experiment is for. In order to add the GUI to 
the tasks listed in the `add_ex_desc_gui_to_tasks` script, run the following commands from the **Anaconda Powershell Prompt**:
```powershell
C:\iblrig\venv\Scripts\.\Activate.ps1
git clone https://github.com/int-brain-lab/iblscripts C:\iblscripts
pip install -r C:\iblscripts\deploy\project_procedure_gui\pp_requirements.txt
```

Within whichever custom task you would like to test this gui, simply add the following lines to `_iblrig_tasks_customTask.py`
* i.e. `C:\iblrig_params\IBL\tasks\_iblrig_tasks_customTask\_iblrig_tasks_customTask.py`

```python
from iblrig.misc import call_exp_desc_gui
call_exp_desc_gui()
```

---
## How to develop on this repository 
This repository is adhering to the following conventions:
* [semantic versioning](https://semver.org/) for consistent version numbering logic
* [gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) for managing branches 
* [flake8](https://flake8.pycqa.org/) for style guide enforcement 

![](README_semver.png)
![](README_gitflow_workflow.png)

Please review these conventions to more easily contribute to the project.

### New feature branches:
- a `new_feature` branch is forked from the current `develop` branch
- the `new_feature` branch is then merged back into the `develop` branch
- the `new_feature` branch will eventually be deleted

### Release candidate branches:
- a release candidate, `rc` branch is a "pre-release" branch for beta testers on production rigs
- the `rc` branch is forked from the `develop` branch
- once the `rc` has been thoroughly tested, it will be merged into `master` and `develop`
- the `rc` branch will eventually be deleted

### Hotfix branches:
- a `hotfix` or `maintenance` branch is forked from `master`
- once the fix has been thoroughly tested, it will get merged back into `master` and `develop`
- the `hotfix` branch will eventually be deleted

#### The dev parameter file
In the root of the repository is a file called `iblrig_params.yml`. To more easily develop on this repository, perform the 
following:
* create a copy of the `iblrig_params.yml` file in the same root directory, but called `iblrig_params_dev.yml`
* make changes to the entries in the file appropriate for your system
  * i.e. `iblrig_local_data_path: "C:\\iblrig_data"` could become `iblrig_local_data_path: "/home/username/my_iblrig_local_data"`

Note: during the ci tests of GitHub Actions, a similar file is created called `iblrig_params_ci.yml`; this is used to accommodate 
the difference in directory structure that this system uses

#### Install Python v3.8 and set up venv for iblrig in Ubuntu 22.04

Instructions are for the assumption that this is for development and that the desired directory to work out of is 
`~/Documents/repos/iblrig`

Installing from deadsnakes repo:
```bash
sudo apt install build-essential --yes
sudo add-apt-repository ppa:deadsnakes/ppa --yes
sudo apt update --yes && sudo apt upgrade --yes
sudo apt install python3.8 python3.8-dev python3.8-venv python3.8-tk --yes
python3.8 -m ensurepip --default-pip --user
python3.8 -m pip install --upgrade pip --user
```

Testing python3.8 venv functionality:
```bash
python3.8 -m venv test_venv
source test_venv/bin/activate
python --version
which python
python -m pip install --upgrade pip wheel
deactivate
rm -rf test_venv
```

---

### Troubleshooting Notes

#### Windows
Disable Microsoft Store associations with `python` command
* Open the Settings or Start menu and search for “App execution aliases” or “Manage app execution aliases” 
* Disable any python entries listed

#### Anaconda
##### Broken Uninstall
* After uninstalling, navigate the file browser to the user home directory (C:\Users\username) and remove all `Anaconda`, 
`.anaconda`, `.conda`, `.condarc`, etc files and folders
  * search the hidden AppData folders as well (different versions of Anaconda stored data in different locations)
* If running the command prompt is no longer functional, run the following command in Powershell:
> Reg Delete "HKCU\Software\Microsoft\Command Processor" /v AutoRun /f
* If Powershell is throwing a warning about an `Activate.ps1` file, remove the profile file from `%userhome%\Documents\Powershell`

##### llvmlite error on ibllib install
While performing a `pip install ibllib` command in a fresh conda environment, an occasional error may occur; `Error: Cannot 
uninstall llvmlite...`. A simple workaround: 
* close all Anaconda Prompts
* open an **Anaconda Powershell Prompt**
* reactivate the ibllib conda environment, `conda activate ibllib`
* run `pip install ibllib`

### Stim display on wrong screen
If the visual stimulus appears on the wrong screen:
* short term, pressing `F11` on the keyboard will unmaximize the window; allowing movement of the stimulus to the correct screen 
* longer term, take note of a file called `C:\iblrig_params\.iblrig_params.json`; within that file is a variable called 
`DISPLAY_IDX`, its value will be set to 0 or 1. If the stimulus screen initially launches on the wrong monitor (PC screen instead 
of iPad screen), then change the value of `DISPLAY_IDX`. Change it to 0 if it was on 1, change it to 1 if it was on 0.
  * Please note, the display index value is something assigned by OS and could potentially change between reboots