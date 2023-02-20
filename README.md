# iblrig v8
Software used to interact with various pieces of specialized hardware for neuroscience data acquisition.

## Code organisation manifesto

### settings and parameters
- settings are relative to the local machine and located in the [settings](settings) directory. 
- task parameters are independent of the hardwware settings and located in the task folders. For example, for biasedCW this is 
  found in this [task_parameters.yaml](iblrig_tasks/_iblrig_tasks_biasedChoiceWorld/task_parameters.yaml)

### task logic code (TODO: Flesh out section)

## Installation on Windows
Software has only been tested on Windows 10. No other version of Windows is supported at this time. The test user account has 
administrative rights.

### Prerequisite Software:
In order to install iblrig on a Windows machine please ensure that the following prerequisite is installed first.
- A fully featured text editor is recommended, something like [Notepad++](https://notepad-plus-plus.org/)
- [Git](https://git-scm.com); it is recommended to set notepad++ as your default editor for git
- [Visual C++ Redistributable for Visual Studio 2015](https://www.microsoft.com/en-us/download/details.aspx?id=48145), this is a 
requirement for the matplotlib python package

Manually download and install the software by following the links above. The other option is to follow the instructions below 
utilizing Chocolatey for a quick command line installation.

#### (Optional) Use Chocolatey to install prerequisite software
[Chocolatey](https://chocolatey.org/) is a command line approach to bring package management to Window. Run the following 
commands from the **Administrator: Windows Powershell** prompt to install prerequisite software by this method:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
choco install vcredist140 --yes
choco install notepadplusplus --yes
choco install git --params "/Editor:Notepad++ /NoShellIntegration" --yes
```
  - Note: git commands will be unavailable until a new session is started; close the current **Administrator: Windows Powershell** 
prompt in order to use git

### Installation Instructions: (Update for v8 once finalized)
- Ensure git and your favorite text editor are already installed by whatever method is desired
- Ensure a stable internet connection is present as several commands will require software to be downloaded

Several important notes:
- There are no supported upgrade paths from previous installations
- User account name is assumed to be `Username`, please modify commands where appropriate
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
git checkout tags/7.2.3
New-Item -ItemType Directory -Force -Path C:\Temp
Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe -OutFile C:\Temp\python-3.8.10-amd64.exe
Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.8.10-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"
C:\Users\<Username>\AppData\Local\Programs\Python\Python38\.\python.exe -m venv C:\iblrig\venv
C:\iblrig\venv\Scripts\.\Activate.ps1
C:\iblrig\venv\scripts\python.exe -m pip install --upgrade pip wheel
pip install --editable . 
pip install --editable ..\iblpybpod
python setup_pybpod.py
cd Bonsai
powershell.exe .\install.ps1
```
  - Note: ONE is installed as part of the iblrig requirement. ONE will need to be configured for your use case. Please review 
the ONE [documentation](https://int-brain-lab.github.io/ONE/) for specifics on how to accomplish this. Then run the following 
command or something similar for your specific setup to test it is working: `python -c "from one.api import ONE; ONE()"`

### Setup instructions for launching the 'Experiment Description GUI'
The 'Experiment Description GUI' is currently being developed in the 
[iblscripts repo](https://github.com/int-brain-lab/iblscripts/tree/master/deploy/project_procedure_gui). 
This GUI is intended to simplify the categorization of an experiment and cleanly define what projects and procedures an 
experiment is for. Please refer to the iblscripts repository for instructions on how to create the separate virtual environment 
and run the GUI.

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

#### Install Python v3.8 and set up venv for iblrig on Ubuntu 22.04

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

#### Install required library for running unit tests on Ubuntu 22.04

PortAudio library is required for the `sounddevice` python package. It can be installed with the following commands
```bash
sudo apt update && sudo apt install -y libportaudio2
```

---

### Troubleshooting Notes

#### Anaconda (base) environment in Powershell
When launching powershell to run any rig code, it is not recommended to have the anaconda base environment active. Run the 
following commands to deactivate the base environment and disable it from auto-activating in the future:    
```powershell
conda deactivate
conda config --set auto_activate_base false
```

#### Windows
Disable Microsoft Store associations with `python` command
* Open the Settings or Start menu and search for “App execution aliases” or “Manage app execution aliases” 
* Disable any python entries listed

#### Stim display on wrong screen
If the visual stimulus appears on the wrong screen:
* short term, pressing `F11` on the keyboard will unmaximize the window; allowing movement of the stimulus to the correct screen 
* longer term, take note of a file called `C:\iblrig_params\.iblrig_params.json`; within that file is a variable called 
`DISPLAY_IDX`, its value will be set to 0 or 1. If the stimulus screen initially launches on the wrong monitor (PC screen instead 
of iPad screen), then change the value of `DISPLAY_IDX`. Change it to 0 if it was on 1, change it to 1 if it was on 0.
  * Please note, the display index value is something assigned by OS and could potentially change between reboots

#### pybpod custom tasks from v6 not running after migrating to v7
After migrating to v7 of the iblrig software, some may encounter a `ModuleNotFoundError: No module named 'iblrig'` error when 
attempting to run their custom tasks. This has to do with the way that pybpod calls python in the pre and post commands. Within 
the `C:\iblrig_params\custom_path\tasks\my_custom_task\` directory, there should be a `my_custom_task.json` file. If this file 
contains any calls to a specific python executable, they must be updated to `C:\iblrig\venv\Scripts\python`.