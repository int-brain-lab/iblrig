# iblrig v7
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
  - The `C:\iblrig` and `C:\iblrig_params` directories are assumed not to exist

Run the following commands from the non-administrative **Windows Powershell** prompt
```powershell
Set-ExecutionPolicy -Scope CurrentUser Unrestricted -Force
cd \
git clone https://github.com/int-brain-lab/iblrig
cd iblrig
New-Item -ItemType Directory -Force -Path C:\Temp
Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe -OutFile C:\Temp\python-3.8.10-amd64.exe
Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.8.10-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"
C:\Users\User\AppData\Local\Programs\Python\Python38\.\python.exe -m venv C:\iblrig\venv
C:\iblrig\venv\Scripts\.\Activate.ps1
C:\iblrig\venv\scripts\python.exe -m pip install --upgrade pip wheel
pip install --editable .
python setup_pybpod.py
cd Bonsai
powershell.exe .\install.ps1
cd ..
.\pybpod.bat
```
  - NOTE: ONE is installed as part of the iblrig requirement. ONE will need to be configured for your use case. Please review 
the ONE [documentation](https://int-brain-lab.github.io/ONE/) for specifics on how to accomplish this. Then run the following 
command or something similar for your specific setup to test: `python -c "from one.api import ONE; ONE()"`

### Running pybpod
To run pybpod and begin data acquisition:
```powershell
C:\iblrig\venv\Scripts\.\Activate.ps1
cd C:\iblrig
.\pybpod.bat
```

#### For easier launching of pybpod
Within the `C:\iblrig` folder there is a `pybpod-Anaconda_Powershell_Prompt.lnk` file that can be copied to the desktop for ease 
of use.
```powershell
Copy-Item "C:\iblrig\pybpod-Anaconda_Powershell_Prompt.lnk" -Destination "$Env:HOMEPATH\Desktop"
```

#### Setup instructions for launching the 'Experiment Description GUI' prior to task launch

The 'Experiment Description GUI' is currently being housed on the iblscripts repo. This GUI is intended to simplify the 
categorization of an experiment and cleanly define what projects and procedures an experiment is for. In order to add the GUI to 
a custom task:

* clone the iblscripts repo: `git clone https://github.com/int-brain-lab/iblscripts`
* launch pybpod
* select the custom task protocol to modify
* click on the plus button to add a "pre command"
* use the drop-down box to select `Execute an external command`
* depending on where the iblscripts repo was clones, enter into the text box something like the following:
  * `python C:\iblscripts\deploy\project_procedure_gui\experiment_form.py`

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
###### v7.0.2 TODO:
- Modify subprocess calls to remove conda
- Correct win32 anaconda/pip issue
- Modify desktop shortcut to powershell script
  - change execution permissions if necessary 
  - change dir
  - .\venv\Scripts\Activate.ps1
  - start-pybpod
- Modify CI
- setup_pybpod by creating/copying json files
  - pybpod_setup.py to create dir structure
  - copy the files
  - verify uuid's are not needed
- change pybpod user_settings.py ingest to an actual parameter file